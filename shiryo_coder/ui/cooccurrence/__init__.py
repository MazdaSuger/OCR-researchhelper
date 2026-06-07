"""共起・関係性可視化 GUI（仕様書 3.6）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.cooccurrence.cooccurrence_panel import CooccurrencePanel

__all__ = ["CooccurrencePanel"]


def __getattr__(name: str):
    if name == "CooccurrencePanel":
        from shiryo_coder.ui.cooccurrence.cooccurrence_panel import CooccurrencePanel

        return CooccurrencePanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
