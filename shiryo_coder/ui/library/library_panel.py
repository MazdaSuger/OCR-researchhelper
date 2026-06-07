"""ライブラリパネル: 全文検索＋メタデータフィルタ＋一覧（ソート可）＋プレビュー。

仕様書 3.2 の中央＋右カラムに相当。`LibraryRepository` を介して検索する。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.library import LibraryRepository

# テーブル列 → 並び替えキー
_COLUMNS = [
    ("タイトル", "title"),
    ("著者", "author"),
    ("年", "year"),
    ("言語", "language"),
    ("信頼度", "confidence"),
    ("コード数", "code_count"),
]


class LibraryPanel(QWidget):
    """史料カタログの検索・一覧・プレビュー。"""

    document_activated = Signal(int)   # ダブルクリック等で開く要求

    def __init__(self, repo: LibraryRepository, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.project_id = project_id
        self._collection_id: int | None = None
        self._order_by = "id"
        self._descending = False

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("全文検索（日本語=trigram / 英語=unicode61）")
        self.search_edit.returnPressed.connect(self.refresh)
        self.search_edit.textChanged.connect(self._on_text_changed)

        self.lang_combo = QComboBox()
        self.lang_combo.currentIndexChanged.connect(self.refresh)

        self.coded_combo = QComboBox()
        self.coded_combo.addItem("コード: すべて", None)
        self.coded_combo.addItem("コード付与済み", True)
        self.coded_combo.addItem("未付与", False)
        self.coded_combo.currentIndexChanged.connect(self.refresh)

        self.year_min = QSpinBox()
        self.year_max = QSpinBox()
        for sb in (self.year_min, self.year_max):
            sb.setRange(0, 3000)
            sb.setSpecialValueText("—")        # 0 は「指定なし」
            sb.valueChanged.connect(self.refresh)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.lang_combo)
        toolbar.addWidget(QLabel("年"))
        toolbar.addWidget(self.year_min)
        toolbar.addWidget(QLabel("〜"))
        toolbar.addWidget(self.year_max)
        toolbar.addWidget(self.coded_combo)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.currentCellChanged.connect(self._on_row_changed)
        self.table.cellDoubleClicked.connect(
            lambda row, _col: self.document_activated.emit(self._row_id(row))
        )

        self.count_label = QLabel("0 件")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(toolbar)
        left_layout.addWidget(self.table, 1)
        left_layout.addWidget(self.count_label)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("史料プレビュー")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setSizes([620, 460])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.reload_filters()
        self.refresh()

    # -- フィルタの再読込（取り込み後など） -------------------------------------
    def reload_filters(self) -> None:
        current = self.lang_combo.currentData()
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        self.lang_combo.addItem("すべての言語", None)
        for lang in self.repo.distinct_languages(self.project_id):
            self.lang_combo.addItem(lang, lang)
        idx = self.lang_combo.findData(current)
        self.lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.lang_combo.blockSignals(False)

    def set_collection(self, collection_id: int | None) -> None:
        self._collection_id = collection_id
        self.refresh()

    # -- 検索実行 ---------------------------------------------------------------
    def refresh(self) -> None:
        results = self.repo.search(
            self.search_edit.text().strip() or None,
            project_id=self.project_id,
            language=self.lang_combo.currentData(),
            year_min=self.year_min.value() or None,
            year_max=self.year_max.value() or None,
            collection_id=self._collection_id,
            coded=self.coded_combo.currentData(),
            order_by=self._order_by,
            descending=self._descending,
        )
        self._populate(results)

    def _populate(self, results) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(results))
        for row, d in enumerate(results):
            conf = f"{d.confidence:.2f}" if d.confidence is not None else "—"
            values = [
                d.title, d.author or "", str(d.year) if d.year else "",
                d.language or "", conf, str(d.code_count),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, d.id)
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self.count_label.setText(f"{len(results)} 件")
        self.preview.clear()

    # -- 行/ヘッダ操作 ----------------------------------------------------------
    def _row_id(self, row: int) -> int:
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else -1

    def _on_row_changed(self, row: int, _col, _prow, _pcol) -> None:
        if row < 0:
            self.preview.clear()
            return
        doc_id = self._row_id(row)
        self.preview.setPlainText(self.repo.document_body(doc_id))

    def _on_header_clicked(self, column: int) -> None:
        key = _COLUMNS[column][1]
        if key == self._order_by:
            self._descending = not self._descending
        else:
            self._order_by = key
            self._descending = False
        self.refresh()

    def _on_text_changed(self, text: str) -> None:
        if not text:               # クリアしたら即時に全件へ戻す
            self.refresh()

    # -- 参照用 -----------------------------------------------------------------
    @property
    def row_count(self) -> int:
        return self.table.rowCount()

    def current_document_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        doc_id = self._row_id(row)
        return doc_id if doc_id >= 0 else None
