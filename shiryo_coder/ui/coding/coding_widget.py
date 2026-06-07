"""コーディングウィジェット: コードブック＋本文ビュー＋ツールバー。

仕様書 3.3: 範囲選択→コード付与、数字キー 1–9 で頻用コード即時付与、
可視化モード切替、コーダー切替（他コーダーを半透明レビュー）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.ui.coding.codebook_tree import CodebookTree
from shiryo_coder.ui.coding.coding_view import MODE_HIGHLIGHT, MODE_UNDERLINE, CodingView


class CodingWidget(QWidget):
    """1 ドキュメントのコーディング作業画面。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.codebook_repo = CodebookRepository(db)
        self.coding_repo = CodingRepository(db)

        self.tree = CodebookTree(self.codebook_repo, project_id)
        self.view = CodingView(self.coding_repo)

        # ツールバー: 可視化モード / コーダー / 付与ボタン
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("下線", MODE_UNDERLINE)
        self.mode_combo.addItem("ハイライト", MODE_HIGHLIGHT)
        self.mode_combo.currentIndexChanged.connect(
            lambda: self.view.set_mode(self.mode_combo.currentData())
        )

        self.coder_combo = QComboBox()
        self.coder_combo.currentIndexChanged.connect(self._on_coder_changed)

        apply_btn = QPushButton("選択範囲にコード付与")
        apply_btn.clicked.connect(self._apply_current_code)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("表示"))
        toolbar.addWidget(self.mode_combo)
        toolbar.addWidget(QLabel("コーダー"))
        toolbar.addWidget(self.coder_combo)
        toolbar.addStretch(1)
        toolbar.addWidget(apply_btn)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addLayout(toolbar)
        center_layout.addWidget(self.view, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(center)
        splitter.setSizes([280, 900])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._install_quick_keys()
        self._reload_coders()

    # -- コーダー --------------------------------------------------------------
    def _reload_coders(self) -> None:
        self.coder_combo.blockSignals(True)
        self.coder_combo.clear()
        rows = self.db.conn.execute(
            "SELECT id, name FROM coder WHERE project_id = ? ORDER BY id", (self.project_id,)
        ).fetchall()
        for row in rows:
            self.coder_combo.addItem(row["name"], row["id"])
        self.coder_combo.blockSignals(False)
        if rows:
            self.view.set_active_coder(rows[0]["id"])

    def _on_coder_changed(self) -> None:
        self.view.set_active_coder(self.coder_combo.currentData())

    @property
    def active_coder(self) -> int | None:
        return self.coder_combo.currentData()

    # -- ドキュメント ----------------------------------------------------------
    def open_document(self, document_id: int) -> None:
        row = self.db.conn.execute(
            "SELECT body FROM document WHERE id = ?", (document_id,)
        ).fetchone()
        body = row["body"] if row else ""
        self.view.set_document(document_id, body, active_coder=self.active_coder)

    # -- コード付与 -------------------------------------------------------------
    def _apply_current_code(self) -> int | None:
        code_id = self.tree.current_code_id()
        return self.view.apply_code(code_id) if code_id is not None else None

    def apply_quick_code(self, number: int) -> int | None:
        """数字キー（1–9）に割り当てたコードを選択範囲へ付与する。"""
        code_id = self.tree.quick_code(number)
        return self.view.apply_code(code_id) if code_id is not None else None

    def _install_quick_keys(self) -> None:
        for n in range(1, 10):
            shortcut = QShortcut(QKeySequence(str(n)), self.view)
            shortcut.activated.connect(lambda n=n: self.apply_quick_code(n))
