"""Gemini / Claude Vision エンジン（API、レイアウト解析＋翻刻補助・くずし字）。

LLM へ画像を渡して翻刻するためのインターフェース足場。実際の API 呼び出しは
プロバイダ SDK と API キーが必要なため、未設定時は EngineUnavailable とする。
座標（バウンディングボックス）は LLM 翻刻では基本的に得られないため空となる。
"""

from __future__ import annotations

import os

from shiryo_coder.modules.ocr.engines.base import EngineUnavailable, OcrEngine
from shiryo_coder.modules.ocr.result import OcrResult

_DEFAULT_PROMPT = (
    "この史料画像を翻刻してください。本文テキストのみを、改行を保ったまま出力してください。"
)


class VisionLLMEngine(OcrEngine):
    """Gemini / Claude などのビジョン LLM を用いた翻刻エンジン。"""

    name = "vision_llm"
    vertical_supported = True

    def __init__(self, *, provider: str = "claude", prompt: str = _DEFAULT_PROMPT) -> None:
        self.provider = provider
        self.prompt = prompt

    def _api_key(self) -> str | None:
        env = "ANTHROPIC_API_KEY" if self.provider == "claude" else "GOOGLE_API_KEY"
        return os.environ.get(env)

    def is_available(self) -> bool:
        return self._api_key() is not None

    def recognize(
        self,
        image,
        *,
        vertical: bool = False,
        language: str | None = None,
    ) -> OcrResult:
        # 実 API 連携は今後の実装ポイント。インターフェースのみ確定させておく。
        raise EngineUnavailable(
            f"ビジョン LLM エンジン（{self.provider}）は未配線です。"
            "API キーを設定し、プロバイダ SDK の呼び出しを実装してください。"
        )
