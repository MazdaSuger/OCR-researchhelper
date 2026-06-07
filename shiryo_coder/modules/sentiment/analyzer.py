"""辞書ベースのセンチメント解析（仕様書 3.4）。

日本語は辞書の最長一致スキャン（形態素解析器なしで動作。Sudachi/spaCy を
`tokenizer` に渡せば差し替え可能）、英語は語境界トークナイズ。否定語が近傍にあれば
極性を反転（oseti 互換の素朴な反転）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from shiryo_coder.modules.sentiment.dictionary import SentimentDictionary
from shiryo_coder.modules.sentiment.normalize import OldToNewNormalizer

_WORD_RE = re.compile(r"[A-Za-z']+")


@dataclass
class Hit:
    word: str
    polarity: float           # 反転適用後
    negated: bool
    start: int


@dataclass
class SentimentScore:
    """1 テキスト分の解析結果。"""

    polarity: float                       # -1..+1（一致語極性の平均）
    positive: int = 0
    negative: int = 0
    hits: list[Hit] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(self.hits)


class SentimentAnalyzer:
    """辞書と正規化器を用いて極性を計算する。"""

    def __init__(
        self,
        dictionary: SentimentDictionary,
        *,
        normalizer: OldToNewNormalizer | None = None,
        negation_window: int = 4,
        tokenizer: Callable[[str], list[tuple[str, int]]] | None = None,
    ) -> None:
        self.dictionary = dictionary
        self.normalizer = normalizer or OldToNewNormalizer()
        self.negation_window = negation_window
        self.tokenizer = tokenizer

    def score_text(self, text: str) -> SentimentScore:
        normalized = self.normalizer.normalize(text)
        if self.tokenizer is not None:
            hits = self._score_tokens(self.tokenizer(normalized))
        elif self.dictionary.language == "en":
            hits = self._score_english(normalized)
        else:
            hits = self._score_japanese(normalized)
        return self._aggregate(hits)

    # -- 日本語: 辞書最長一致スキャン ------------------------------------------
    def _score_japanese(self, text: str) -> list[Hit]:
        words = self.dictionary.words
        max_len = self.dictionary.max_word_len
        hits: list[Hit] = []
        i = 0
        n = len(text)
        while i < n:
            matched = None
            for length in range(min(max_len, n - i), 0, -1):
                candidate = text[i : i + length]
                if candidate in words:
                    matched = (candidate, length)
                    break
            if matched is None:
                i += 1
                continue
            word, length = matched
            base = words[word]
            negated = self._has_negation_after(text, i + length)
            hits.append(Hit(word, -base if negated else base, negated, i))
            i += length
        return hits

    def _has_negation_after(self, text: str, pos: int) -> bool:
        window = text[pos : pos + self.negation_window]
        return any(neg in window for neg in self.dictionary.negations)

    # -- 英語: 語トークナイズ＋否定の先読み -----------------------------------
    def _score_english(self, text: str) -> list[Hit]:
        tokens = [(m.group(0).lower(), m.start()) for m in _WORD_RE.finditer(text)]
        return self._score_tokens(tokens)

    def _score_tokens(self, tokens: list[tuple[str, int]]) -> list[Hit]:
        hits: list[Hit] = []
        negations = self.dictionary.negations
        for idx, (surface, start) in enumerate(tokens):
            base = self.dictionary.words.get(surface)
            if base is None:
                continue
            # 直前 negation_window トークンに否定語があれば反転
            window = tokens[max(0, idx - self.negation_window) : idx]
            negated = any(w in negations or w.endswith("n't") for w, _ in window)
            hits.append(Hit(surface, -base if negated else base, negated, start))
        return hits

    # -- 集計 ------------------------------------------------------------------
    @staticmethod
    def _aggregate(hits: list[Hit]) -> SentimentScore:
        if not hits:
            return SentimentScore(0.0)
        total = sum(h.polarity for h in hits)
        polarity = max(-1.0, min(1.0, total / len(hits)))
        positive = sum(1 for h in hits if h.polarity > 0)
        negative = sum(1 for h in hits if h.polarity < 0)
        return SentimentScore(polarity, positive, negative, hits)
