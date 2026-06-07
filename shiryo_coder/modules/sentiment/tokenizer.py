"""形態素解析器（仕様書 3.4）。

辞書ベース解析の前段に形態素解析を挟み、活用語を辞書形（lemma）へ正規化して
照合できるようにする。日本語は Sudachi、英語は spaCy（任意）。いずれも未導入なら
`available_tokenizer` は None を返し、解析器は内蔵の辞書スキャンにフォールバックする。

トークナイザは `text -> list[(token, start)]` の callable。token は辞書照合に使う
表層（既定では辞書形 lemma）。
"""

from __future__ import annotations

import importlib.util


class SudachiTokenizer:
    """Sudachi による日本語形態素解析（辞書形を返す）。"""

    def __init__(self, *, mode: str = "C", normalized: bool = False) -> None:
        from sudachipy import dictionary, tokenizer

        self._tokenizer = dictionary.Dictionary().create()
        self._mode = {
            "A": tokenizer.Tokenizer.SplitMode.A,
            "B": tokenizer.Tokenizer.SplitMode.B,
            "C": tokenizer.Tokenizer.SplitMode.C,
        }[mode]
        self._normalized = normalized

    def __call__(self, text: str) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        for m in self._tokenizer.tokenize(text, self._mode):
            token = m.normalized_form() if self._normalized else m.dictionary_form()
            out.append((token, m.begin()))
        return out


class SpacyTokenizer:
    """spaCy による英語トークナイズ（lemma を返す）。"""

    def __init__(self, model: str = "en_core_web_sm") -> None:
        import spacy

        try:
            self._nlp = spacy.load(model, disable=["ner", "parser"])
        except OSError:
            self._nlp = spacy.blank("en")

    def __call__(self, text: str) -> list[tuple[str, int]]:
        return [(tok.lemma_.lower(), tok.idx) for tok in self._nlp(text)]


def sudachi_available() -> bool:
    return importlib.util.find_spec("sudachipy") is not None and (
        importlib.util.find_spec("sudachidict_core") is not None
        or importlib.util.find_spec("sudachidict_small") is not None
    )


def spacy_available() -> bool:
    return importlib.util.find_spec("spacy") is not None


def available_tokenizer(language: str):
    """言語に対して利用可能な形態素解析器を返す（無ければ None）。"""
    if language == "ja" and sudachi_available():
        return SudachiTokenizer()
    if language == "en" and spacy_available():
        return SpacyTokenizer()
    return None
