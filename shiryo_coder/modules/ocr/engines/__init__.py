"""OCR エンジンのレジストリ。

UI 上でドキュメント単位／一括でエンジンを選択できるよう（仕様書 3.1）、
名前 → エンジン生成関数のマップを提供する。エンジン本体は遅延 import し、
レジストリの import で重い依存（cv2/pytesseract 等）を要求しないようにする。
"""

from __future__ import annotations

from typing import Callable

from shiryo_coder.modules.ocr.engines.base import EngineUnavailable, OcrEngine


def _tesseract() -> OcrEngine:
    from shiryo_coder.modules.ocr.engines.tesseract import Tesseract5Engine

    return Tesseract5Engine()


def _ndlocr() -> OcrEngine:
    from shiryo_coder.modules.ocr.engines.ndlocr import NdlOcrLiteEngine

    return NdlOcrLiteEngine()


def _google_vision() -> OcrEngine:
    from shiryo_coder.modules.ocr.engines.cloud_vision import GoogleVisionEngine

    return GoogleVisionEngine()


def _vision_llm() -> OcrEngine:
    from shiryo_coder.modules.ocr.engines.vision_llm import VisionLLMEngine

    return VisionLLMEngine()


#: エンジン名 → ファクトリ
ENGINE_FACTORIES: dict[str, Callable[[], OcrEngine]] = {
    "tesseract": _tesseract,
    "ndlocr_lite": _ndlocr,
    "google_vision": _google_vision,
    "vision_llm": _vision_llm,
}


def engine_names() -> list[str]:
    """登録済みエンジン名の一覧。"""
    return list(ENGINE_FACTORIES)


def get_engine(name: str) -> OcrEngine:
    """名前からエンジンを生成する。"""
    try:
        factory = ENGINE_FACTORIES[name]
    except KeyError:
        raise KeyError(
            f"未知のエンジン '{name}'。利用可能: {', '.join(ENGINE_FACTORIES)}"
        ) from None
    return factory()


def available_engines() -> dict[str, bool]:
    """各エンジンの可用性（依存・認証が揃っているか）を返す。"""
    status: dict[str, bool] = {}
    for name, factory in ENGINE_FACTORIES.items():
        try:
            status[name] = factory().is_available()
        except Exception:
            status[name] = False
    return status


__all__ = [
    "EngineUnavailable",
    "OcrEngine",
    "ENGINE_FACTORIES",
    "engine_names",
    "get_engine",
    "available_engines",
]
