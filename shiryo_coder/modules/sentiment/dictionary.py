"""評価極性辞書（仕様書 3.4）。

高村「単語感情極性対応表」(語\\t -1..+1) や 東北大評価極性辞書(語\\t posi/nega) の
読み込み、VADER 互換 TSV、内蔵シード辞書（日英）を扱う。否定語も保持する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# 内蔵シード辞書（小規模だが史料文脈を意識）。本格運用では外部辞書を load する。
_JA_SEED = {
    "喜び": 0.8, "嬉しい": 0.8, "良い": 0.6, "善": 0.6, "忠": 0.5, "忠義": 0.7,
    "名誉": 0.6, "勝利": 0.7, "平和": 0.6, "安寧": 0.6, "功": 0.4, "賢": 0.5,
    "仁": 0.5, "栄光": 0.7, "繁栄": 0.6,
    "悲しい": -0.8, "苦しい": -0.7, "悪い": -0.6, "不忠": -0.8, "逆賊": -0.9,
    "敗北": -0.7, "戦乱": -0.6, "罪": -0.6, "恥": -0.6, "怒り": -0.6, "憎い": -0.7,
    "滅亡": -0.7, "死": -0.4, "災い": -0.6, "混乱": -0.5,
}
_JA_NEGATIONS = {"ない", "ず", "ぬ", "なし", "ありません", "無", "不", "非", "ざる"}

_EN_SEED = {
    "good": 0.7, "great": 0.8, "happy": 0.8, "victory": 0.7, "peace": 0.6,
    "honor": 0.6, "glory": 0.7, "prosperity": 0.6, "loyal": 0.6, "wise": 0.5,
    "bad": -0.7, "sad": -0.8, "evil": -0.9, "defeat": -0.7, "war": -0.4,
    "death": -0.5, "traitor": -0.9, "crime": -0.6, "shame": -0.6, "chaos": -0.5,
}
_EN_NEGATIONS = {"not", "no", "never", "none", "without", "n't", "cannot"}


@dataclass
class SentimentDictionary:
    """語 → 極性値（-1..+1）と否定語集合。"""

    language: str
    words: dict[str, float] = field(default_factory=dict)
    negations: set[str] = field(default_factory=set)
    name: str = "custom"

    def polarity(self, word: str) -> float | None:
        return self.words.get(word)

    def is_negation(self, word: str) -> bool:
        return word in self.negations

    def merge(self, other: "SentimentDictionary") -> "SentimentDictionary":
        """別辞書を重ねた新しい辞書を返す（other が優先）。"""
        merged = dict(self.words)
        merged.update(other.words)
        return SentimentDictionary(
            language=self.language,
            words=merged,
            negations=self.negations | other.negations,
            name=f"{self.name}+{other.name}",
        )

    @property
    def max_word_len(self) -> int:
        return max((len(w) for w in self.words), default=1)

    # -- 構築 ------------------------------------------------------------------
    @classmethod
    def builtin(cls, language: str) -> "SentimentDictionary":
        if language == "ja":
            return cls("ja", dict(_JA_SEED), set(_JA_NEGATIONS), name="builtin-ja")
        if language == "en":
            return cls("en", dict(_EN_SEED), set(_EN_NEGATIONS), name="builtin-en")
        return cls(language, {}, set(), name=f"empty-{language}")

    @classmethod
    def from_takamura(cls, source: str | Path, *, language: str = "ja") -> "SentimentDictionary":
        """高村式（語\\t極性値[-1..1]）を読み込む。区切りはタブ or コロン。"""
        words: dict[str, float] = {}
        for line in _iter_lines(source):
            parts = line.replace("\t", ":").split(":")
            if len(parts) >= 2:
                try:
                    words[parts[0].strip()] = float(parts[-1])
                except ValueError:
                    continue
        neg = _JA_NEGATIONS if language == "ja" else _EN_NEGATIONS
        return cls(language, words, set(neg), name="takamura")

    @classmethod
    def from_tohoku(cls, source: str | Path, *, language: str = "ja") -> "SentimentDictionary":
        """東北大式（語\\t posi/nega/...）を読み込み ±1 に写像する。"""
        words: dict[str, float] = {}
        for line in _iter_lines(source):
            parts = line.split("\t")
            if len(parts) >= 2:
                label = parts[1].strip().lower()
                value = {"p": 1.0, "posi": 1.0, "positive": 1.0,
                         "n": -1.0, "nega": -1.0, "negative": -1.0}.get(label)
                if value is not None:
                    words[parts[0].strip()] = value
        neg = _JA_NEGATIONS if language == "ja" else _EN_NEGATIONS
        return cls(language, words, set(neg), name="tohoku")


def _iter_lines(source: str | Path):
    text = source
    if isinstance(source, Path) or (
        isinstance(source, str) and "\n" not in source and Path(source).exists()
    ):
        text = Path(source).read_text(encoding="utf-8")
    for line in str(text).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            yield line
