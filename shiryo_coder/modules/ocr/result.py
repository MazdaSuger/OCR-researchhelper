"""OCR 結果の表現（テキスト・信頼度・バウンディングボックス）。

手動校正画面（仕様書 3.1）で「バウンディングボックス↔テキスト相互ジャンプ」を
実現するため、語・行単位の座標を保持できる構造にしている。
依存ライブラリを持たない純データ型なので、どの環境でも import 可能。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BoundingBox:
    """画像上の矩形（左上原点、ピクセル単位）。"""

    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def union(self, other: "BoundingBox") -> "BoundingBox":
        """2 つの矩形を包含する最小矩形を返す。"""
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        right = max(self.right, other.right)
        bottom = max(self.bottom, other.bottom)
        return BoundingBox(x, y, right - x, bottom - y)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


@dataclass
class OcrWord:
    """認識された 1 語（または 1 トークン）。"""

    text: str
    bbox: BoundingBox
    confidence: float          # 0.0–1.0
    line_index: int = 0


@dataclass
class OcrLine:
    """認識された 1 行（語の集合）。"""

    text: str
    bbox: BoundingBox
    words: list[OcrWord] = field(default_factory=list)


@dataclass
class OcrResult:
    """1 ページ分の OCR 結果。

    `text` はエンジンの整形済み出力（本文用）、`words`/`lines` は座標付きの
    トークンで、校正 UI のハイライト対応に用いる。
    """

    text: str
    engine: str
    confidence: float | None = None
    words: list[OcrWord] = field(default_factory=list)
    lines: list[OcrLine] = field(default_factory=list)

    @staticmethod
    def build_lines(words: list[OcrWord], *, join: str = " ") -> list[OcrLine]:
        """語を line_index でまとめて行を構築する。"""
        if not words:
            return []
        lines: list[OcrLine] = []
        bucket: dict[int, list[OcrWord]] = {}
        for w in words:
            bucket.setdefault(w.line_index, []).append(w)
        for idx in sorted(bucket):
            group = bucket[idx]
            bbox = group[0].bbox
            for w in group[1:]:
                bbox = bbox.union(w.bbox)
            text = join.join(w.text for w in group)
            lines.append(OcrLine(text=text, bbox=bbox, words=group))
        return lines

    @classmethod
    def from_words(
        cls,
        words: list[OcrWord],
        *,
        engine: str,
        text: str | None = None,
        line_join: str = " ",
    ) -> "OcrResult":
        """語リストから結果を構築する（行・平均信頼度を自動算出）。"""
        lines = cls.build_lines(words, join=line_join)
        if text is None:
            text = "\n".join(line.text for line in lines)
        confs = [w.confidence for w in words if w.confidence >= 0.0]
        confidence = sum(confs) / len(confs) if confs else None
        return cls(
            text=text,
            engine=engine,
            confidence=confidence,
            words=words,
            lines=lines,
        )
