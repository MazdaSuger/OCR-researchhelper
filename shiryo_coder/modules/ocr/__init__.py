"""3.1 OCR 取り込みモジュール。

責務:
- 入力: 画像（jpg/png/tiff）・PDF（複数頁分割）・ZIP 一括・ディレクトリ
- 前処理: 傾き補正・二値化・ノイズ除去（OpenCV）
- エンジン切替: Tesseract 5 / NDLOCR-Lite / Google Cloud Vision / Gemini・Claude Vision
- 言語/方向自動判定 → ユーザー確認 → バッチ OCR（QThreadPool）
- 手動校正（元画像↔テキストの相互ジャンプ用に語・行単位の座標を保持）
- .md 保存（YAML Front Matter に language/era/source_image/ocr_engine/confidence）

公開 API:
- 結果型: `OcrResult`, `OcrWord`, `OcrLine`, `BoundingBox`
- エンジン: `get_engine`, `engine_names`, `available_engines`, `OcrEngine`, `EngineUnavailable`
- パイプライン（遅延ロード）: `OcrPipeline`, `IngestedDocument`

重い依存（cv2/pytesseract/pypdfium2）は各サブモジュール側で読み込むため、
`import shiryo_coder.modules.ocr` 自体は軽量な結果型とエンジンレジストリのみを読み込む。
パイプラインは初回アクセス時に遅延 import する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shiryo_coder.modules.ocr.engines import (
    EngineUnavailable,
    OcrEngine,
    available_engines,
    engine_names,
    get_engine,
)
from shiryo_coder.modules.ocr.result import (
    BoundingBox,
    OcrLine,
    OcrResult,
    OcrWord,
)

if TYPE_CHECKING:  # 型チェック時のみ（実行時は __getattr__ で遅延ロード）
    from shiryo_coder.modules.ocr.pipeline import IngestedDocument, OcrPipeline

__all__ = [
    "BoundingBox",
    "OcrLine",
    "OcrResult",
    "OcrWord",
    "OcrEngine",
    "EngineUnavailable",
    "get_engine",
    "engine_names",
    "available_engines",
    "OcrPipeline",
    "IngestedDocument",
]


def __getattr__(name: str):
    """`OcrPipeline` / `IngestedDocument` を遅延 import で公開する。"""
    if name in ("OcrPipeline", "IngestedDocument"):
        from shiryo_coder.modules.ocr import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
