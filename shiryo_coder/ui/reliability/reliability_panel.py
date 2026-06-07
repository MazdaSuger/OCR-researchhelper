"""信頼性検証パネル: 文書・コード・コーダー・粒度を選び一致率を算出する。

仕様書 3.5: Cohen/Fleiss/Krippendorff、算出単位選択、不一致抽出（CSV）、研修モード。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.reliability import ReliabilityRepository, disagreements_to_csv

_GRANULARITIES = [("文字単位", "character"), ("文単位", "sentence"), ("セグメント単位", "segment")]


class ReliabilityPanel(QWidget):
    """一致率の算出・不一致抽出・研修フィードバック。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.repo = ReliabilityRepository(db)
        self.last_result = None
        self.last_disagreements = []

        self.doc_combo = QComboBox()
        self.code_combo = QComboBox()
        self.gran_combo = QComboBox()
        for label, value in _GRANULARITIES:
            self.gran_combo.addItem(label, value)

        self.coder_list = QListWidget()
        self.coder_list.setMaximumHeight(120)

        self.training_check = QCheckBox("研修モード（先頭=マスター、2 名目=研修者）")

        form = QFormLayout()
        form.addRow("史料", self.doc_combo)
        form.addRow("コード", self.code_combo)
        form.addRow("算出単位", self.gran_combo)
        form.addRow("コーダー", self.coder_list)
        form.addRow("", self.training_check)

        compute_btn = QPushButton("一致率を計算")
        compute_btn.clicked.connect(self.compute)
        self.export_btn = QPushButton("不一致を CSV 出力")
        self.export_btn.clicked.connect(self._export_clicked)
        self.export_btn.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addWidget(compute_btn)
        buttons.addWidget(self.export_btn)
        buttons.addStretch(1)

        self.result_label = QLabel("—")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["範囲", "テキスト", "ラベル"])
        self.table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.result_label)
        layout.addWidget(self.table, 1)

        self.reload()

    # -- データ読み込み ---------------------------------------------------------
    def reload(self) -> None:
        self.doc_combo.clear()
        for row in self.db.conn.execute(
            "SELECT id, title FROM document WHERE project_id = ? ORDER BY id",
            (self.project_id,),
        ):
            self.doc_combo.addItem(row["title"], row["id"])

        self.code_combo.clear()
        for row in self.db.conn.execute(
            "SELECT id, name FROM code WHERE project_id = ? ORDER BY sort_order, id",
            (self.project_id,),
        ):
            self.code_combo.addItem(row["name"], row["id"])

        self.coder_list.clear()
        for row in self.db.conn.execute(
            "SELECT id, name FROM coder WHERE project_id = ? ORDER BY id",
            (self.project_id,),
        ):
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.coder_list.addItem(item)

    # -- 選択補助（テスト/プログラム用） ---------------------------------------
    def selected_coders(self) -> list[int]:
        return [
            self.coder_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.coder_list.count())
            if self.coder_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def check_coders(self, coder_ids: list[int]) -> None:
        for i in range(self.coder_list.count()):
            item = self.coder_list.item(i)
            state = (
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in coder_ids
                else Qt.CheckState.Unchecked
            )
            item.setCheckState(state)

    # -- 計算 ------------------------------------------------------------------
    def compute(self) -> None:
        doc = self.doc_combo.currentData()
        code = self.code_combo.currentData()
        coders = self.selected_coders()
        gran = self.gran_combo.currentData()
        if doc is None or code is None or len(coders) < 2:
            self.result_label.setText("史料・コード・コーダー（2 名以上）を選択してください。")
            return

        if self.training_check.isChecked() and len(coders) >= 2:
            fb = self.repo.training_feedback(doc, code, coders[0], coders[1], gran)
            self.result_label.setText(
                f"研修フィードバック: κ={fb.kappa:.3f}  "
                f"一致(TP)={fb.true_positive} / 見落とし(FN)={fb.false_negative} / "
                f"過剰(FP)={fb.false_positive}"
            )
            self.last_disagreements = fb.missed + fb.extra
        else:
            result = self.repo.compute(doc, code, coders, gran)
            text = f"{result.method} = {result.value:.3f}（{result.n_units} 単位, {gran}）"
            if "krippendorff_alpha" in result.extra:
                text += f"  / Krippendorff α = {result.extra['krippendorff_alpha']:.3f}"
            self.result_label.setText(text)
            self.last_result = result
            self.last_disagreements = self.repo.disagreements(doc, code, coders, gran)

        self._fill_table(self.last_disagreements)
        self.export_btn.setEnabled(bool(self.last_disagreements))

    def _fill_table(self, disagreements) -> None:
        self.table.setRowCount(len(disagreements))
        for row, d in enumerate(disagreements):
            self.table.setItem(row, 0, QTableWidgetItem(f"{d.char_start}–{d.char_end}"))
            self.table.setItem(row, 1, QTableWidgetItem(d.text))
            labels = ", ".join(f"{cid}:{v}" for cid, v in d.labels.items())
            self.table.setItem(row, 2, QTableWidgetItem(labels))

    def disagreement_csv(self) -> str:
        names = {
            self.coder_list.item(i).data(Qt.ItemDataRole.UserRole): self.coder_list.item(i).text()
            for i in range(self.coder_list.count())
        }
        return disagreements_to_csv(self.last_disagreements, names)

    def _export_clicked(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "CSV 出力", "disagreements.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write(self.disagreement_csv())
