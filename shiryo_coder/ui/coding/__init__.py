"""コーディング GUI（仕様書 3.3）。

- `CodebookTree`: 階層コードツリー（色・DnD 親子変更・コンテキストメニュー）
- `CodingView`: 本文へのコード可視化＋範囲選択コーディング
- `CodingWidget`: 上記＋ツールバー（可視化モード・コーダー・数字キー駆動）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.coding.codebook_tree import CodebookTree
    from shiryo_coder.ui.coding.coding_view import CodingView
    from shiryo_coder.ui.coding.coding_widget import CodingWidget

__all__ = ["CodebookTree", "CodingView", "CodingWidget"]


def __getattr__(name: str):
    if name == "CodebookTree":
        from shiryo_coder.ui.coding.codebook_tree import CodebookTree

        return CodebookTree
    if name == "CodingView":
        from shiryo_coder.ui.coding.coding_view import CodingView

        return CodingView
    if name == "CodingWidget":
        from shiryo_coder.ui.coding.coding_widget import CodingWidget

        return CodingWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
