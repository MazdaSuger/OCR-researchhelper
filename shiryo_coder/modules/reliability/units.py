"""一致判定の算出単位（文字／文／セグメント）への変換。仕様書 3.5。

コーディング結果（重なり許容のセグメント群）を、選んだ粒度の単位ごとの
「あるコードを付与したか（0/1）」のラベル列に変換する。
"""

from __future__ import annotations

import re

# 文末とみなす区切り（日本語・英語）
_SENTENCE_BOUNDARY = re.compile(r"[。．！？!?]+|\n+")
# 段落区切り（空行）
_PARAGRAPH_BOUNDARY = re.compile(r"\n\s*\n")

Span = tuple[int, int]


def character_spans(length: int) -> list[Span]:
    """各文字を 1 単位とする。"""
    return [(i, i + 1) for i in range(length)]


def sentence_spans(text: str) -> list[Span]:
    """本文を文単位に分割した (start, end) のリストを返す（区切り文字を含む）。"""
    spans: list[Span] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        end = match.end()
        if end > start and text[start:end].strip():
            spans.append((start, end))
        start = end
    if start < len(text) and text[start:].strip():
        spans.append((start, len(text)))
    return spans


def paragraph_spans(text: str) -> list[Span]:
    """本文を段落（空行区切り）に分割した (start, end) のリストを返す。"""
    spans: list[Span] = []
    start = 0
    for match in _PARAGRAPH_BOUNDARY.finditer(text):
        end = match.start()
        if text[start:end].strip():
            spans.append((start, end))
        start = match.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans or ([(0, len(text))] if text.strip() else [])


def segment_atomic_spans(segments, length: int) -> list[Span]:
    """全コーディング境界で本文を原子区間に分割する（セグメント粒度）。"""
    boundaries = {0, length}
    for seg in segments:
        boundaries.add(max(0, min(seg.char_start, length)))
        boundaries.add(max(0, min(seg.char_end, length)))
    points = sorted(boundaries)
    return [(points[i], points[i + 1]) for i in range(len(points) - 1) if points[i + 1] > points[i]]


def _coded(coder_segments, code_id: int, span: Span, min_overlap_ratio: float) -> int:
    """コーダーが指定単位にそのコードを付与しているかを 0/1 で返す。"""
    us, ue = span
    unit_len = ue - us
    if unit_len <= 0:
        return 0
    for seg in coder_segments:
        if seg.code_id != code_id:
            continue
        overlap = min(ue, seg.char_end) - max(us, seg.char_start)
        if overlap <= 0:
            continue
        if min_overlap_ratio <= 0.0 or overlap / unit_len >= min_overlap_ratio:
            return 1
    return 0


def coder_binary_labels(
    segments_by_coder: dict[int, list],
    code_id: int,
    units: list[Span],
    *,
    min_overlap_ratio: float = 0.0,
) -> dict[int, list[int]]:
    """コーダー → 単位ごとの 0/1 ラベル列。"""
    return {
        coder_id: [
            _coded(segs, code_id, span, min_overlap_ratio) for span in units
        ]
        for coder_id, segs in segments_by_coder.items()
    }
