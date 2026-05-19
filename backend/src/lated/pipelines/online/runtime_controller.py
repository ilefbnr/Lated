# =============================================================================
# lated.pipelines.online.runtime_controller — admin control surface (MVP)
# =============================================================================
#
# Minimal but real:
#   - status()              -> current paused flag, model version, threshold rev
#   - reload_thresholds()   -> defers to ConfigManager.reload_thresholds
#   - pause() / resume()    -> toggle a flag the orchestrator can consult
#
# `swap_model()` is explicitly unsupported in this phase: it raises a clear
# error rather than pretending. The interface stays in place so a later phase
# can wire it without callers changing.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class RuntimeStatus:
    paused: bool
    model_version: str
    threshold_revision: int
    last_action_at: str
    last_action_actor: str | None


class RuntimeControllerError(RuntimeError):
    """Raised when an admin action is not supported in this phase."""


class RuntimeController:
    """Admin-facing controller for the running online pipeline."""

    def __init__(self, components, event_store=None, config_manager=None):
        self.components = components
        self.event_store = event_store
        self.config_manager = config_manager
        self._paused = False
        self._threshold_revision = 0
        self._last_action_at = datetime.now(timezone.utc).isoformat()
        self._last_action_actor: str | None = None

    def status(self) -> RuntimeStatus:
        lm = getattr(self.components, "lm_inference", None)
        model_version = getattr(lm, "model_version", "unknown")
        return RuntimeStatus(
            paused=self._paused,
            model_version=model_version,
            threshold_revision=self._threshold_revision,
            last_action_at=self._last_action_at,
            last_action_actor=self._last_action_actor,
        )

    def pause(self, actor: str) -> RuntimeStatus:
        self._paused = True
        return self._record(actor, action="pause", payload={})

    def resume(self, actor: str) -> RuntimeStatus:
        self._paused = False
        return self._record(actor, action="resume", payload={})

    def reload_thresholds(self, actor: str) -> RuntimeStatus:
        if self.config_manager is None:
            raise RuntimeControllerError(
                "reload_thresholds requires a ConfigManager handle."
            )
        self.config_manager.reload_thresholds()
        self._threshold_revision += 1
        return self._record(actor, action="reload_thresholds", payload={
            "threshold_revision": self._threshold_revision,
        })

    def swap_model(self, path: str, signature_path: str, actor: str) -> RuntimeStatus:
        # Real swap requires torch + a verified artifact loader hook into
        # the running TGNNInference. Out of scope for this phase.
        raise RuntimeControllerError(
            "swap_model is not implemented in the current phase."
        )

    @property
    def paused(self) -> bool:
        return self._paused

    def _record(self, actor: str, action: str, payload: dict[str, Any]) -> RuntimeStatus:
        self._last_action_at = datetime.now(timezone.utc).isoformat()
        self._last_action_actor = actor
        if self.event_store is not None:
            try:
                self.event_store.append(
                    actor=actor,
                    action=f"runtime.{action}",
                    target="online_pipeline",
                    payload=payload,
                )
            except Exception:
                # Audit-log failure must not block control plane.
                pass
        return self.status()
