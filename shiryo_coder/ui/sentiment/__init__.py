"""センチメント分析 GUI（仕様書 3.4）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.ui.sentiment.sentiment_panel import SentimentPanel

__all__ = ["SentimentPanel"]


def __getattr__(name: str):
    if name == "SentimentPanel":
        from shiryo_coder.ui.sentiment.sentiment_panel import SentimentPanel

        return SentimentPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
