# =============================================================================
# lated.supervision.discovery_workflow — discovery jobs, uploads, and history
# =============================================================================

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lated.discovery.discovery_service import DiscoveryService


class DiscoveryWorkflow:
    """Local discovery orchestration with persisted history and uploads."""

    def __init__(
        self,
        *,
        backend_root: Path,
        baseline_path: Path,
        registry_path: Path,
        event_store,
    ):
        self.backend_root = backend_root
        self.baseline_path = baseline_path
        self.registry_path = registry_path
        self.event_store = event_store
        self.data_dir = backend_root / "data" / "discovery_jobs"
        self.upload_dir = backend_root / "data" / "uploads"
        self.history_path = self.data_dir / "history.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def list_history(self) -> list[dict[str, Any]]:
        return list(reversed(self._read_history()))

    def latest(self) -> dict[str, Any] | None:
        rows = self._read_history()
        return rows[-1] if rows else None

    def run_job(
        self,
        *,
        config,
        source_kind: str,
        source_value: str,
        actor: str,
        mode: str = "passive",
    ) -> dict[str, Any]:
        job_id = f"discovery-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).isoformat()
        source_path = self._resolve_source(source_kind, source_value)

        service = DiscoveryService(
            config.discovery,
            source_path=source_path,
            baseline_path=self.baseline_path,
            registry_path=self.registry_path,
            env=str(config.env),
        )
        baseline = service.run()

        record = {
            "job_id": job_id,
            "status": "completed",
            "mode": mode,
            "source_kind": source_kind,
            "source_value": source_value,
            "resolved_source_path": str(source_path),
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "generated_at": baseline.created_at,
            "host_count": len(baseline.nodes),
            "edge_count": len(baseline.edges),
            "subnet_count": len(baseline.subnets),
            "gateway_count": len(baseline.gateways),
            "service_count": len(baseline.services),
            "baseline_path": str(self.baseline_path),
            "registry_path": str(self.registry_path),
        }
        history = self._read_history()
        history.append(record)
        self._write_history(history)
        self.event_store.append(
            actor=actor,
            action="discovery.run",
            target=job_id,
            payload=record,
        )
        return record

    def upload(self, filename: str, payload: bytes) -> dict[str, str]:
        safe_name = Path(filename).name
        target = self.upload_dir / f"{uuid.uuid4().hex[:8]}-{safe_name}"
        target.write_bytes(payload)
        return {
            "filename": safe_name,
            "stored_path": str(target),
        }

    def _resolve_source(self, source_kind: str, source_value: str) -> Path:
        raw = Path(source_value)
        if raw.is_absolute():
            return raw
        return self.backend_root / raw

    def _read_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _write_history(self, rows: list[dict[str, Any]]) -> None:
        self.history_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
