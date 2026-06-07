"""NDLOCR-Lite エンジン（ローカル、近世以前〜近代日本語・縦書き）。

仕様書 3.1 の推奨ローカルエンジン。実体は別途モデル配布（NDL ラボ）が必要なため、
本リポジトリではインターフェース足場とし、未導入時は EngineUnavailable とする。
"""

from __future__ import annotations

import importlib.util

from shiryo_coder.modules.ocr.engines.base import EngineUnavailable, OcrEngine
from shiryo_coder.modules.ocr.result import OcrResult


class NdlOcrLiteEngine(OcrEngine):
    name = "ndlocr_lite"
    vertical_supported = True

    def is_available(self) -> bool:
        # 連携パッケージ（仮称 `ndlocr`）が import 可能かで判定する。
        return importlib.util.find_spec("ndlocr") is not None

    def recognize(
        self,
        image,
        *,
        vertical: bool = False,
        language: str | None = None,
    ) -> OcrResult:
        raise EngineUnavailable(
            "NDLOCR-Lite モデルが未導入です。NDL ラボのモデルを配置し、"
            "本エンジンの recognize を配線してください。"
        )
