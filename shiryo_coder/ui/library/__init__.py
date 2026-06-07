"""ライブラリ管理 GUI（仕様書 3.2）。

`LibraryPanel`（検索バー＋メタデータフィルタ＋ソート可能な一覧＋プレビュー）を
遅延 import で公開する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.library.library_panel import LibraryPanel

__all__ = ["LibraryPanel"]


def __getattr__(name: str):
    if name == "LibraryPanel":
        from shiryo_coder.ui.library.library_panel import LibraryPanel

        return LibraryPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
