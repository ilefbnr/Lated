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
    EdgeFeatures,
    NodeFeatures,
    SCHEMA_VERSION,
    TemporalSnapshot,
)
from lated.detection.tgnn.model_loader import ModelLoader
from lated.detection.tgnn.tgnn_inference import PLACEHOLDER_MODEL_VERSION, TGNNInference
from lated.graph.graph_builder import GraphBuilder


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


def _snapshot_stream() -> list[TemporalSnapshot]:
    base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    flows = []
    for i in range(8):
        flows.append(_flow(f"f{i}", base + timedelta(seconds=i), "host-a", f"host-{i}", dst_port=1000 + i))
    # a single benign flow in a separate window
    flows.append(_flow("fz", base + timedelta(seconds=70), "host-b", "host-c"))
    return GraphBuilder(window_seconds=30).run(flows)


def test_tgnn_placeholder_emits_deterministic_lm_scores() -> None:
    snapshots = _snapshot_stream()
    a = TGNNInference().run(snapshots)
    b = TGNNInference().run(snapshots)
    assert [s.model_dump(mode="json") for s in a] == [s.model_dump(mode="json") for s in b]
    assert all(0.0 <= score.score <= 1.0 for score in a)
    assert any(score.subject_host == "host-a" for score in a)


def test_tgnn_placeholder_carries_contributing_edges() -> None:
    snapshots = _snapshot_stream()
    scores = TGNNInference().run(snapshots)
    attacker_scores = [s for s in scores if s.subject_host == "host-a"]
    assert attacker_scores, "host-a should emit at least one LMScore"
    sample = attacker_scores[0]
    assert sample.model_version == PLACEHOLDER_MODEL_VERSION
    # all contributing edges originate from the subject
    assert all(src == sample.subject_host for src, _dst in sample.contributing_edges)


def test_tgnn_inference_does_not_crash_on_bad_snapshot() -> None:
    valid = _snapshot_stream()
    # Bad snapshot: a node_features dict missing the expected host -> _score_snapshot
    # handles it safely. We pass a hand-crafted snapshot with empty features that
    # references a host id only in the nodes list.
    broken = TemporalSnapshot(
        snapshot_id="snap-broken",
        window_start=datetime(2024, 1, 2, tzinfo=timezone.utc),
        window_end=datetime(2024, 1, 2, 0, 0, 30, tzinfo=timezone.utc),
        nodes=["host-x"],
        edges=[],
        edge_features={},
        node_features={},
    )
    inf = TGNNInference()
    out = inf.run([broken, *valid])
    # the bad snapshot must not poison the stream — valid snapshots still score
    assert any(s.subject_host == "host-a" for s in out)


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
