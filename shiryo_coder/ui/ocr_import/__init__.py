"""OCR 取り込みワークフローの GUI（仕様書 3.1）。

- `PreprocessPreviewWidget`: 前処理の個別調整＋プレビュー
- `ImportSettings` / `ImportSettingsDialog`: エンジン・言語・方向・前処理の確認
- `BatchProgressWidget`: QThreadPool バッチの進捗表示

いずれも PySide6 を要するため遅延 import で公開する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.ocr_import.batch_progress import BatchProgressWidget
    from shiryo_coder.ui.ocr_import.import_dialog import ImportSettings, ImportSettingsDialog
    from shiryo_coder.ui.ocr_import.preprocess_preview import PreprocessPreviewWidget

__all__ = [
    "PreprocessPreviewWidget",
    "ImportSettings",
    "ImportSettingsDialog",
    "BatchProgressWidget",
]


def __getattr__(name: str):
    if name == "PreprocessPreviewWidget":
        from shiryo_coder.ui.ocr_import.preprocess_preview import PreprocessPreviewWidget

        return PreprocessPreviewWidget
    if name in ("ImportSettings", "ImportSettingsDialog"):
        from shiryo_coder.ui.ocr_import import import_dialog

        return getattr(import_dialog, name)
    if name == "BatchProgressWidget":
        from shiryo_coder.ui.ocr_import.batch_progress import BatchProgressWidget

        return BatchProgressWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
