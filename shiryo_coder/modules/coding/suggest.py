"""AI 支援コーディング（類似セグメント検索）。仕様書 3.3。

文埋め込み → 既存コードの代表セグメントとのコサイン類似度で候補コードを提示する。
外部モデルに依存しないよう、既定では文字 n-gram の軽量埋め込みを用いる（決定的・
オフライン）。より高精度な埋め込みが必要なら `Embedder` を差し替える設計。
提示はあくまで候補であり、採用はユーザー承認制（このモジュールは推薦のみ）。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

Vector = dict[str, float]


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> Vector:
        ...


class CharNGramEmbedder:
    """文字 n-gram の頻度ベクトル（言語非依存・CJK にも有効）。"""

    def __init__(self, n: int = 2) -> None:
        self.n = n

    def embed(self, text: str) -> Vector:
        cleaned = re.sub(r"\s+", "", text)
        vec: Vector = {}
        if len(cleaned) < self.n:
            if cleaned:
                vec[cleaned] = 1.0
            return vec
        for i in range(len(cleaned) - self.n + 1):
            gram = cleaned[i : i + self.n]
            vec[gram] = vec.get(gram, 0.0) + 1.0
        return vec


def cosine(a: Vector, b: Vector) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    if dot == 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb)


def _centroid(vectors: list[Vector]) -> Vector:
    centroid: Vector = {}
    for vec in vectors:
        for k, v in vec.items():
            centroid[k] = centroid.get(k, 0.0) + v
    n = len(vectors)
    if n > 1:
        for k in centroid:
            centroid[k] /= n
    return centroid


@dataclass
class Suggestion:
    code_id: int
    score: float


def suggest_codes(
    text: str,
    code_examples: dict[int, list[str]],
    *,
    embedder: Embedder | None = None,
    top_k: int = 3,
    min_score: float = 0.05,
) -> list[Suggestion]:
    """選択テキストに対し、既存コードの代表例との類似度で候補コードを返す。

    - `code_examples`: code_id → 代表セグメントのテキスト群
      （`CodingRepository.representative_texts` の出力）。
    - 戻り値: スコア降順の候補（min_score 未満は除外、上位 top_k）。
    """
    embedder = embedder or CharNGramEmbedder()
    query = embedder.embed(text)
    if not query:
        return []

    scored: list[Suggestion] = []
    for code_id, examples in code_examples.items():
        vectors = [embedder.embed(e) for e in examples if e]
        vectors = [v for v in vectors if v]
        if not vectors:
            continue
        score = cosine(query, _centroid(vectors))
        if score >= min_score:
            scored.append(Suggestion(code_id=code_id, score=score))

    scored.sort(key=lambda s: (s.score, -s.code_id), reverse=True)
    return scored[:top_k]
