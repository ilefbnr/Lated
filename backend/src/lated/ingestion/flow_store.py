# =============================================================================
# lated.ingestion.flow_store — forensic-replay JSONL store for CanonicalFlow
# =============================================================================
#
# Append-only JSON Lines store at a stable on-disk path. Each accepted
# CanonicalFlow is written as exactly one line, with sorted JSON keys so the
# file is bit-stable across replays.
#
# This is the simplest persistence shape that satisfies the forensic-replay
# requirement: cat-friendly, grep-friendly, no migration on schema bumps,
# and trivially loadable by downstream phases.
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from lated.common.schemas import CanonicalFlow
from lated.ingestion.canonical_schema import CanonicalSchema


class FlowStore:
    """Append-only JSONL forensic store for CanonicalFlow records."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, flow: CanonicalFlow) -> None:
        payload = CanonicalSchema.to_storage(flow)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    def append_many(self, flows) -> int:
        count = 0
        with self.path.open("a", encoding="utf-8") as handle:
            for flow in flows:
                payload = CanonicalSchema.to_storage(flow)
                handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
                count += 1
        return count

    def read_all(self) -> Iterator[CanonicalFlow]:
        if not self.path.exists():
            return iter(())
        return self._iter_lines()

    def _iter_lines(self) -> Iterator[CanonicalFlow]:
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                yield CanonicalSchema.from_storage(json.loads(line))

    def count(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
