# =============================================================================
# tests/test_tgnn.py — LM detector + model loader coverage
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lated.common.exceptions import ModelLoadError
from lated.common.schemas import (
    CanonicalFlow,
    SCHEMA_VERSION,
)
from lated.detection.tgnn.model_loader import ModelLoader
from lated.detection.tgnn.tgnn_inference import TGNNInference


def _flow(
    flow_id: str,
    ts: datetime,
    src: str,
    dst: str,
    dst_port: int = 445,
    packets: int = 10,
    bytes_: int = 1000,
) -> CanonicalFlow:
    return CanonicalFlow(
        flow_id=flow_id,
        ts=ts,
        src_host=src,
        dst_host=dst,
        src_port=51200,
        dst_port=dst_port,
        protocol="tcp",
        duration=0.5,
        packet_count=packets,
        byte_count=bytes_,
        source_sensor="zeek",
    )


def test_tgnn_inference_without_runtime_emits_no_scores() -> None:
    """With no checkpoint loaded, score_flows returns [] — no fallback."""
    base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    flows = [
        _flow(f"f{i}", base + timedelta(seconds=i), "host-a", f"host-{i}", dst_port=1000 + i)
        for i in range(8)
    ]
    inf = TGNNInference()
    assert inf.has_runtime is False
    assert inf.score_flows(flows) == []


def test_model_loader_accepts_signed_artifact(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake-weights")

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "model_version": "tgnn-1.0.0",
        "feature_set": ["bytes", "packets", "port_entropy", "fan_out"],
    }
    (tmp_path / "model.json").write_text(json.dumps(metadata), encoding="utf-8")

    secret = "test-key"
    digest = hmac.new(secret.encode(), artifact.read_bytes(), hashlib.sha256).hexdigest()
    (tmp_path / "model.pt.sig").write_text(digest, encoding="utf-8")

    loaded = ModelLoader(secret_key=secret).load(
        artifact,
        required_features=["bytes", "fan_out"],
    )
    assert loaded.model_version == "tgnn-1.0.0"
    assert loaded.metadata["schema_version"] == SCHEMA_VERSION


def test_model_loader_rejects_missing_signature(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake")
    (tmp_path / "model.json").write_text(json.dumps({"schema_version": SCHEMA_VERSION}), encoding="utf-8")

    try:
        ModelLoader(secret_key="k").load(artifact)
    except ModelLoadError as exc:
        assert "Signature" in str(exc) or "sig" in str(exc).lower()
    else:
        raise AssertionError("Missing signature must raise ModelLoadError.")


def test_model_loader_rejects_incompatible_schema(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake")
    (tmp_path / "model.json").write_text(
        json.dumps({"schema_version": "0.0.0", "model_version": "x"}), encoding="utf-8"
    )
    digest = hmac.new(b"k", artifact.read_bytes(), hashlib.sha256).hexdigest()
    (tmp_path / "model.pt.sig").write_text(digest, encoding="utf-8")

    try:
        ModelLoader(secret_key="k").load(artifact)
    except ModelLoadError as exc:
        assert "schema_version" in str(exc)
    else:
        raise AssertionError("Incompatible schema must raise ModelLoadError.")


def test_model_loader_rejects_tampered_payload(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake")
    (tmp_path / "model.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "model_version": "x"}), encoding="utf-8"
    )
    (tmp_path / "model.pt.sig").write_text("0" * 64, encoding="utf-8")

    try:
        ModelLoader(secret_key="k").load(artifact)
    except ModelLoadError as exc:
        assert "signature" in str(exc).lower()
    else:
        raise AssertionError("Tampered payload must raise ModelLoadError.")


def test_tgnn_branch_isolated_from_recon_module() -> None:
    inf_src = Path(
        Path(__file__).resolve().parents[1]
        / "src"
        / "lated"
        / "detection"
        / "tgnn"
        / "tgnn_inference.py"
    ).read_text(encoding="utf-8")
    assert "lated.detection.recon" not in inf_src
