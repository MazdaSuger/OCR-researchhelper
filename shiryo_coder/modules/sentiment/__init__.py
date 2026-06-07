"""3.4 センチメント分析モジュール（辞書ベース）。

責務:
- 評価極性辞書（高村/東北大/VADER 形式の読込、内蔵シード、カスタム史料辞書）
- 史料語彙の正規化（旧字旧仮名 → 新字新仮名）
- 辞書ベース解析（最長一致スキャン＋否定反転、形態素解析器は差し替え可能）
- 分析単位（文・段落・コードセグメント・文書全体）ごとの極性、保存
- 可視化用集計（年代別時系列、コード別の極性分布）

公開 API:
- `SentimentDictionary`, `OldToNewNormalizer`, `SentimentAnalyzer`, `SentimentScore`
- `LexiconRepository`, `SentimentRepository`, `UnitSentiment`, `UNITS`
"""

from shiryo_coder.modules.sentiment.analyzer import SentimentAnalyzer, SentimentScore
from shiryo_coder.modules.sentiment.dictionary import SentimentDictionary
from shiryo_coder.modules.sentiment.lexicon import LexiconRepository
from shiryo_coder.modules.sentiment.normalize import OldToNewNormalizer
from shiryo_coder.modules.sentiment.sentiment_repo import (
    UNITS,
    SentimentRepository,
    UnitSentiment,
)
from shiryo_coder.modules.sentiment.tokenizer import (
    SpacyTokenizer,
    SudachiTokenizer,
    available_tokenizer,
    spacy_available,
    sudachi_available,
)

__all__ = [
    "SentimentDictionary",
    "OldToNewNormalizer",
    "SentimentAnalyzer",
    "SentimentScore",
    "LexiconRepository",
    "SentimentRepository",
    "UnitSentiment",
    "UNITS",
    "SudachiTokenizer",
    "SpacyTokenizer",
    "available_tokenizer",
    "sudachi_available",
    "spacy_available",
]
