"""手動校正画面（仕様書 3.1）。

- `CorrectionModel`: Qt 非依存の同期モデル（ヒットテスト・校正テキスト保持）
- `CorrectionWidget`: 左＝画像＋行ボックス／右＝編集テキストの双方向同期ウィジェット

`CorrectionWidget` は PySide6 を要するため遅延 import で公開する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shiryo_coder.ui.correction.model import CorrectionLine, CorrectionModel

if TYPE_CHECKING:
    from shiryo_coder.ui.correction.correction_widget import CorrectionWidget

__all__ = ["CorrectionModel", "CorrectionLine", "CorrectionWidget"]


def __getattr__(name: str):
    if name == "CorrectionWidget":
        from shiryo_coder.ui.correction.correction_widget import CorrectionWidget

        return CorrectionWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
