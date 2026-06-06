"""3.1 OCR 取り込みモジュール。

責務:
- 入力: 画像（jpg/png/tiff）・PDF（複数頁分割）・ZIP 一括
- 前処理: 傾き補正・二値化・ノイズ除去（OpenCV）
- エンジン切替: NDLOCR-Lite / Tesseract 5 / Google Cloud Vision / Gemini・Claude Vision
- 言語/方向自動判定 → ユーザー確認 → バッチ OCR（QThreadPool）
- 手動校正（元画像↔テキストの相互ジャンプ）
- .md 保存（YAML Front Matter に language/era/source_image/ocr_engine/confidence）

雛形段階では `OcrEngine` プロトコルのみ定義する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class OcrResult:
    """OCR 1ページ分の結果。"""

    text: str
    confidence: float | None = None
    # 将来: バウンディングボックス、行単位の座標など


@runtime_checkable
class OcrEngine(Protocol):
    """OCR エンジンの共通インターフェース。"""

    name: str

    def recognize(self, image_path: str, *, vertical: bool = False) -> OcrResult:
        """画像ファイルを認識してテキストを返す。"""
        ...
