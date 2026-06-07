"""共同作業 GUI（仕様書 3.7）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.collaboration.collaboration_panel import CollaborationPanel

__all__ = ["CollaborationPanel"]


def __getattr__(name: str):
    if name == "CollaborationPanel":
        from shiryo_coder.ui.collaboration.collaboration_panel import CollaborationPanel

        return CollaborationPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
