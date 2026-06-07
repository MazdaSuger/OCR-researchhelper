"""エクスポート GUI（仕様書 3.8）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.export.export_panel import ExportPanel

__all__ = ["ExportPanel"]


def __getattr__(name: str):
    if name == "ExportPanel":
        from shiryo_coder.ui.export.export_panel import ExportPanel

        return ExportPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
