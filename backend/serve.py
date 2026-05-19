"""Tiny dev launcher for the LateD supervision API.

Usage (from backend/):
    python serve.py
or:
    uvicorn serve:app --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lated.common.config_manager import ConfigManager  # noqa: E402
from lated.supervision.api.app import create_app  # noqa: E402


def _build_app():
    config = ConfigManager.load(
        str(ROOT / "config" / "settings.yaml"),
        str(ROOT / "config" / "detection_thresholds.yaml"),
    )
    return create_app(config)


app = _build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
