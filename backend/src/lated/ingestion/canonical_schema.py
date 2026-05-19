# =============================================================================
# lated.ingestion.canonical_schema — helpers around CanonicalFlow
# =============================================================================
#
# Thin shell around common.schemas.CanonicalFlow. All heavy validation lives
# in the Pydantic model itself; this module just provides ergonomic
# constructors + a forensic-store-friendly serializer pair.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from lated.common.exceptions import FlowValidationError
from lated.common.schemas import CanonicalFlow


class CanonicalSchema:
    """Construction / serialization helpers for CanonicalFlow."""

    @staticmethod
    def from_normalized(d: dict[str, Any]) -> CanonicalFlow:
        try:
            return CanonicalFlow.model_validate(d)
        except ValidationError as exc:
            raise FlowValidationError(f"CanonicalFlow validation failed: {exc.errors()}") from exc

    @staticmethod
    def to_storage(flow: CanonicalFlow) -> dict[str, Any]:
        payload = flow.model_dump(mode="json")
        if isinstance(payload.get("ts"), datetime):
            payload["ts"] = payload["ts"].isoformat()
        return payload

    @staticmethod
    def from_storage(d: dict[str, Any]) -> CanonicalFlow:
        return CanonicalSchema.from_normalized(d)
