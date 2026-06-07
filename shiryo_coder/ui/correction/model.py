"""手動校正画面の状態モデル（純 Python、Qt 非依存）。

仕様書 3.1「手動校正画面: 左ペインに元画像（クリックで対応行ハイライト）、
右ペインに認識テキスト。バウンディングボックス↔テキスト相互ジャンプ」。

ヒットテスト・校正テキストの保持・選択状態を Qt から切り離して持つことで、
ロジックを GUI なしでテストできるようにしている。
"""

from __future__ import annotations

from dataclasses import dataclass

from shiryo_coder.modules.ocr.result import BoundingBox, OcrLine, OcrResult


@dataclass
class CorrectionLine:
    """校正対象の 1 行（バウンディングボックス＋原文＋校正後テキスト）。"""

    index: int
    bbox: BoundingBox
    original: str
    corrected: str

    @property
    def edited(self) -> bool:
        return self.corrected != self.original


class CorrectionModel:
    """元画像の行ボックスと認識テキストの対応を保持するモデル。"""

    def __init__(self, result: OcrResult) -> None:
        self._engine = result.engine
        self.lines: list[CorrectionLine] = [
            CorrectionLine(i, line.bbox, line.text, line.text)
            for i, line in enumerate(result.lines)
        ]
        self.selected_index: int | None = None

    # -- 編集 ------------------------------------------------------------------
    def set_corrected(self, index: int, text: str) -> None:
        self.lines[index].corrected = text

    def select(self, index: int | None) -> None:
        if index is not None and not (0 <= index < len(self.lines)):
            raise IndexError(index)
        self.selected_index = index

    # -- 参照 ------------------------------------------------------------------
    def corrected_text(self) -> str:
        """校正後の全文（行を改行で連結）。"""
        return "\n".join(line.corrected for line in self.lines)

    def is_dirty(self) -> bool:
        """いずれかの行が編集済みか。"""
        return any(line.edited for line in self.lines)

    def line_at_point(self, x: float, y: float) -> int | None:
        """画像座標 (x, y) を含む行のインデックスを返す。

        複数のボックスが重なる場合は面積最小（最も具体的）の行を返す。
        """
        best: int | None = None
        best_area = None
        for line in self.lines:
            b = line.bbox
            if b.x <= x < b.right and b.y <= y < b.bottom:
                area = b.w * b.h
                if best_area is None or area < best_area:
                    best, best_area = line.index, area
        return best

    def to_result(self) -> OcrResult:
        """校正後テキストを反映した OcrResult を生成する。"""
        lines = [
            OcrLine(text=cl.corrected, bbox=cl.bbox)
            for cl in self.lines
        ]
        return OcrResult(
            text=self.corrected_text(),
            engine=self._engine,
            lines=lines,
        )
