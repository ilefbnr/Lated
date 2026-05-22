# =============================================================================
# lated.detection.tgnn.model_loader — signed-artifact metadata loader (MVP)
# =============================================================================
#
# Real trained TGNN artifacts (torch state_dict) are out of scope for this
# phase. What we DO provide and test here is the supply-chain guard:
#
#   - the .pt file must exist,
#   - a detached .sig must exist alongside it,
#   - a sidecar .json must carry compatible metadata (schema_version, feature
#     set). Missing or incompatible metadata -> ModelLoadError.
#
# Once a real model lands, swap the placeholder body in `load()` for a torch
# state_dict load — the verification layer above stays unchanged.
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lated.common.exceptions import ModelLoadError
from lated.common.schemas import SCHEMA_VERSION


@dataclass(frozen=True)
class ModelArtifact:
    path: Path
    signature_path: Path
    metadata_path: Path
    metadata: dict
    model_version: str
    sha256: str
    node_mapping_path: Path | None = None


def load_unsigned_artifact(
    model_path: str | Path,
    node_mapping_path: str | Path | None = None,
    model_version: str = "dev-unsigned",
) -> ModelArtifact:
    """Dev-friendly loader: bypass signature/metadata sidecars.

    Production code should keep using `ModelLoader.load()`. This helper exists
    to plug a local .pt file into the runtime when you just want to see the
    model produce real scores (e.g. against the bundled PicoDomain dataset).
    """
    model = Path(model_path)
    if not model.exists():
        raise ModelLoadError(f"Model artifact not found: {model}")
    payload = model.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    mapping = Path(node_mapping_path) if node_mapping_path is not None else None
    return ModelArtifact(
        path=model,
        signature_path=Path(str(model) + ".sig"),
        metadata_path=model.with_suffix(".json"),
        metadata={"schema_version": "dev", "feature_set": []},
        model_version=model_version,
        sha256=digest,
        node_mapping_path=mapping,
    )


class ModelLoader:
    """Verifies a TGNN artifact + its sidecar signature and metadata."""

    def __init__(self, secret_key: str, expected_schema_version: str = SCHEMA_VERSION):
        if not secret_key:
            raise ModelLoadError("ModelLoader requires a non-empty secret_key.")
        self.secret_key = secret_key
        self.expected_schema_version = expected_schema_version

    def load(
        self,
        model_path: str | Path,
        signature_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        required_features: Iterable[str] | None = None,
    ) -> ModelArtifact:
        model = Path(model_path)
        if not model.exists():
            raise ModelLoadError(f"Model artifact not found: {model}")

        sig = Path(signature_path) if signature_path is not None else model.with_suffix(model.suffix + ".sig")
        if not sig.exists():
            raise ModelLoadError(f"Signature sidecar missing: {sig}")

        meta = Path(metadata_path) if metadata_path is not None else model.with_suffix(".json")
        if not meta.exists():
            raise ModelLoadError(f"Metadata sidecar missing: {meta}")

        payload = model.read_bytes()
        expected = hmac.new(self.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        actual = sig.read_text(encoding="utf-8").strip()
        if not hmac.compare_digest(expected, actual):
            raise ModelLoadError("Model signature mismatch.")

        metadata = json.loads(meta.read_text(encoding="utf-8"))
        if metadata.get("schema_version") != self.expected_schema_version:
            raise ModelLoadError(
                f"Model schema_version {metadata.get('schema_version')!r} != expected "
                f"{self.expected_schema_version!r}"
            )

        required = list(required_features or [])
        if required:
            declared = set(metadata.get("feature_set", []))
            missing = [feat for feat in required if feat not in declared]
            if missing:
                raise ModelLoadError(f"Model missing required features: {missing}")

        digest = hashlib.sha256(payload).hexdigest()
        return ModelArtifact(
            path=model,
            signature_path=sig,
            metadata_path=meta,
            metadata=metadata,
            model_version=str(metadata.get("model_version", "unknown")),
            sha256=digest,
        )
