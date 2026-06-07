"""Google Cloud Vision エンジン（API、高精度バックアップ）。

`google-cloud-vision` SDK と認証情報（GOOGLE_APPLICATION_CREDENTIALS）が
設定されている場合のみ利用可能。未設定時は EngineUnavailable を送出する。
"""

from __future__ import annotations

import os

from shiryo_coder.modules.ocr.engines.base import EngineUnavailable, OcrEngine
from shiryo_coder.modules.ocr.engines.tesseract import _to_pil
from shiryo_coder.modules.ocr.result import BoundingBox, OcrResult, OcrWord


class GoogleVisionEngine(OcrEngine):
    name = "google_vision"
    vertical_supported = True

    def is_available(self) -> bool:
        try:
            import google.cloud.vision  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

    def recognize(
        self,
        image,
        *,
        vertical: bool = False,
        language: str | None = None,
    ) -> OcrResult:
        if not self.is_available():
            raise EngineUnavailable(
                "Google Cloud Vision を使うには `pip install google-cloud-vision` と "
                "GOOGLE_APPLICATION_CREDENTIALS の設定が必要です。"
            )
        import io

        from google.cloud import vision

        buffer = io.BytesIO()
        _to_pil(image).convert("RGB").save(buffer, format="PNG")
        client = vision.ImageAnnotatorClient()
        hints = [language] if language in ("ja", "en") else None
        ctx = vision.ImageContext(language_hints=hints) if hints else None
        response = client.document_text_detection(
            image=vision.Image(content=buffer.getvalue()), image_context=ctx
        )
        if response.error.message:  # pragma: no cover - API 依存
            raise EngineUnavailable(f"Vision API エラー: {response.error.message}")

        words: list[OcrWord] = []
        line_index = 0
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        text = "".join(s.text for s in word.symbols)
                        xs = [v.x for v in word.bounding_box.vertices]
                        ys = [v.y for v in word.bounding_box.vertices]
                        words.append(
                            OcrWord(
                                text=text,
                                bbox=BoundingBox(
                                    min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                                ),
                                confidence=float(word.confidence),
                                line_index=line_index,
                            )
                        )
                    line_index += 1
        return OcrResult.from_words(
            words, engine=self.name, text=response.full_text_annotation.text.strip()
        )
