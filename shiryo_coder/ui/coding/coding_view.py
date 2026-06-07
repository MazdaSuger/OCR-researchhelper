"""コーディングビュー（中央ペイン）。

本文を表示し、コード付与セグメントを可視化（下線色分け / ハイライト塗り）。
マウス範囲選択 → コード付与。重複・部分重なりを許容。他コーダーの付与は半透明表示。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from shiryo_coder.modules.coding import CodingRepository
from shiryo_coder.modules.coding.coding import assign_layers

# 可視化モード
MODE_UNDERLINE = "underline"
MODE_HIGHLIGHT = "highlight"


def _qcolor(hex_color: str | None, alpha: int) -> QColor:
    c = QColor(hex_color) if hex_color else QColor("#888888")
    c.setAlpha(alpha)
    return c


class CodingView(QTextEdit):
    """本文＋コード可視化。"""

    selection_coded = Signal(int)        # 付与された segment id

    def __init__(self, coding: CodingRepository, parent=None) -> None:
        super().__init__(parent)
        self.coding = coding
        self.document_id: int | None = None
        self.active_coder: int | None = None
        self.mode = MODE_UNDERLINE
        self._segments = []
        self.setReadOnly(True)           # テキストは編集不可、選択は可
        self.setUndoRedoEnabled(False)

    # -- ドキュメント設定 -------------------------------------------------------
    def set_document(self, document_id: int, body: str, *, active_coder: int | None = None) -> None:
        self.document_id = document_id
        self.active_coder = active_coder
        self.setPlainText(body)
        self.reload()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self._refresh_highlights()

    def set_active_coder(self, coder_id: int | None) -> None:
        self.active_coder = coder_id
        self._refresh_highlights()

    def reload(self) -> None:
        if self.document_id is None:
            return
        self._segments = self.coding.segments_for_document(self.document_id)
        self._refresh_highlights()

    # -- コード付与 -------------------------------------------------------------
    def selection_range(self) -> tuple[int, int] | None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return None
        return cursor.selectionStart(), cursor.selectionEnd()

    def apply_code(self, code_id: int) -> int | None:
        """現在の選択範囲に指定コードを付与する。"""
        rng = self.selection_range()
        if rng is None or self.document_id is None or self.active_coder is None:
            return None
        seg_id = self.coding.add_coding(self.document_id, code_id, self.active_coder, *rng)
        self.reload()
        self.selection_coded.emit(seg_id)
        return seg_id

    # -- 可視化 ----------------------------------------------------------------
    def _refresh_highlights(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        layers = assign_layers(self._segments)
        for seg in self._segments:
            # 他コーダーの付与は半透明でレビュー表示
            is_active = self.active_coder is None or seg.coder_id == self.active_coder
            alpha = 70 if is_active else 30
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            if self.mode == MODE_HIGHLIGHT:
                fmt.setBackground(_qcolor(seg.color, alpha))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                fmt.setUnderlineColor(_qcolor(seg.color, 255 if is_active else 120))
                # レイヤーが深いほど少し背景も付け、積層を視認しやすくする
                if layers.get(seg.id, 0) > 0:
                    fmt.setBackground(_qcolor(seg.color, 25))
            sel.format = fmt
            cursor = self.textCursor()
            cursor.setPosition(seg.char_start)
            cursor.setPosition(seg.char_end, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cursor
            selections.append(sel)
        self.setExtraSelections(selections)

    @property
    def visible_segment_count(self) -> int:
        return len(self.extraSelections())
