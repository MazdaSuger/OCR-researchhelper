"""信頼性検証 GUI（仕様書 3.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.reliability.reliability_panel import ReliabilityPanel

__all__ = ["ReliabilityPanel"]


def __getattr__(name: str):
    if name == "ReliabilityPanel":
        from shiryo_coder.ui.reliability.reliability_panel import ReliabilityPanel

        return ReliabilityPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
