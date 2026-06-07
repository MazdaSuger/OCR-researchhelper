"""右ペイン: 行単位で編集可能な認識テキスト一覧。

行を選択すると `line_selected(index)`、セルを編集すると `text_edited(index, text)`
を送出する。編集済みの行は背景色で示す。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from shiryo_coder.ui.correction.model import CorrectionModel

_EDITED_BG = QColor(255, 245, 200)


class LineTextView(QTableWidget):
    """行 × 校正テキストのテーブル。"""

    line_selected = Signal(int)
    text_edited = Signal(int, str)

    def __init__(self, model: CorrectionModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._syncing = False

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["行", "校正テキスト"])
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)

        self._populate()
        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)

    def _populate(self) -> None:
        self._syncing = True
        self.setRowCount(len(self._model.lines))
        for line in self._model.lines:
            num = QTableWidgetItem(str(line.index + 1))
            num.setFlags(num.flags() & ~Qt.ItemFlag.ItemIsEditable)
            num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(line.index, 0, num)

            text = QTableWidgetItem(line.corrected)
            text.setToolTip(f"原文: {line.original}")
            self.setItem(line.index, 1, text)
        self.resizeColumnToContents(0)
        self._syncing = False

    # -- シグナル ---------------------------------------------------------------
    def _on_current_cell_changed(self, row: int, _col, _prow, _pcol) -> None:
        if self._syncing or row < 0:
            return
        self.line_selected.emit(row)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._syncing or item.column() != 1:
            return
        row = item.row()
        text = item.text()
        self._model.set_corrected(row, text)
        self._apply_edited_style(row)
        self.text_edited.emit(row, text)

    def _apply_edited_style(self, row: int) -> None:
        item = self.item(row, 1)
        if item is None:
            return
        self._syncing = True
        item.setBackground(_EDITED_BG if self._model.lines[row].edited else QColor(Qt.GlobalColor.white))
        self._syncing = False

    # -- 外部からの選択 ---------------------------------------------------------
    def select_row(self, index: int) -> None:
        """シグナルを発火させずに行を選択する（相互ジャンプ用）。"""
        self._syncing = True
        self.setCurrentCell(index, 1)
        self.selectRow(index)
        self._syncing = False
