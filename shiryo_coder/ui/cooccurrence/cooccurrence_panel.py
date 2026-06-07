"""共起・関係性可視化パネル（仕様書 3.6）。

共起マトリクス（スコープ切替）＋ネットワーク HTML 出力＋意味的関係の定義、
およびヒートマップ（コード×メタデータ）をタブで提供する。
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.cooccurrence import (
    CooccurrenceRepository,
    HeatmapRepository,
    RelationRepository,
    build_graph,
    to_html,
)

_SCOPES = [("重なり（同一セグメント）", "overlap"), ("同一段落", "paragraph"),
           ("距離 N 文字以内", "distance")]
_DIMENSIONS = [("年代", "year"), ("著者", "author"), ("時代", "era"), ("言語", "language")]


class CooccurrencePanel(QWidget):
    """共起マトリクス・ネットワーク・関係定義・ヒートマップ。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.co_repo = CooccurrenceRepository(db)
        self.rel_repo = RelationRepository(db)
        self.heat_repo = HeatmapRepository(db)
        self.last_result = None

        tabs = QTabWidget()
        tabs.addTab(self._build_cooccur_tab(), "共起マトリクス")
        tabs.addTab(self._build_heatmap_tab(), "ヒートマップ")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self._reload_codes()

    # -- 共起タブ --------------------------------------------------------------
    def _build_cooccur_tab(self) -> QWidget:
        self.scope_combo = QComboBox()
        for label, value in _SCOPES:
            self.scope_combo.addItem(label, value)
        self.distance_spin = QSpinBox()
        self.distance_spin.setRange(0, 100000)
        self.distance_spin.setValue(20)

        compute_btn = QPushButton("共起を計算")
        compute_btn.clicked.connect(self.compute_matrix)
        self.export_btn = QPushButton("ネットワーク HTML 出力")
        self.export_btn.clicked.connect(self._export_clicked)
        self.export_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("スコープ"))
        controls.addWidget(self.scope_combo)
        controls.addWidget(QLabel("距離"))
        controls.addWidget(self.distance_spin)
        controls.addWidget(compute_btn)
        controls.addWidget(self.export_btn)
        controls.addStretch(1)

        self.matrix_table = QTableWidget(0, 0)

        # 意味的関係の定義
        self.rel_a = QComboBox()
        self.rel_b = QComboBox()
        self.rel_type = QLineEdit()
        self.rel_type.setPlaceholderText("関係（対立/包含/因果…）")
        add_rel_btn = QPushButton("関係を追加")
        add_rel_btn.clicked.connect(self.add_relation)
        self.rel_list = QListWidget()

        rel_controls = QHBoxLayout()
        rel_controls.addWidget(QLabel("関係:"))
        rel_controls.addWidget(self.rel_a)
        rel_controls.addWidget(self.rel_b)
        rel_controls.addWidget(self.rel_type)
        rel_controls.addWidget(add_rel_btn)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(controls)
        layout.addWidget(self.matrix_table, 1)
        layout.addLayout(rel_controls)
        layout.addWidget(self.rel_list)
        return tab

    def _build_heatmap_tab(self) -> QWidget:
        self.dim_combo = QComboBox()
        for label, value in _DIMENSIONS:
            self.dim_combo.addItem(label, value)
        heatmap_btn = QPushButton("ヒートマップを作成")
        heatmap_btn.clicked.connect(self.build_heatmap)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("ディメンション"))
        controls.addWidget(self.dim_combo)
        controls.addWidget(heatmap_btn)
        controls.addStretch(1)

        self.heatmap_table = QTableWidget(0, 0)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(controls)
        layout.addWidget(self.heatmap_table, 1)
        return tab

    # -- コード一覧 ------------------------------------------------------------
    def _reload_codes(self) -> None:
        self._codes = self.db.conn.execute(
            "SELECT id, name FROM code WHERE project_id = ? ORDER BY sort_order, id",
            (self.project_id,),
        ).fetchall()
        for combo in (self.rel_a, self.rel_b):
            combo.clear()
            for row in self._codes:
                combo.addItem(row["name"], row["id"])
        self._refresh_relations()

    # -- 共起計算 --------------------------------------------------------------
    def compute_matrix(self) -> None:
        scope = self.scope_combo.currentData()
        result = self.co_repo.matrix(
            self.project_id, scope=scope, distance=self.distance_spin.value()
        )
        self.last_result = result
        self._fill_matrix(result)
        self.export_btn.setEnabled(bool(result.code_ids))

    def _fill_matrix(self, result) -> None:
        ids = result.code_ids
        names = [result.code_names[i] for i in ids]
        self.matrix_table.setRowCount(len(ids))
        self.matrix_table.setColumnCount(len(ids))
        self.matrix_table.setHorizontalHeaderLabels(names)
        self.matrix_table.setVerticalHeaderLabels(names)
        for r, a in enumerate(ids):
            for c, b in enumerate(ids):
                value = result.frequencies.get(a, 0) if a == b else result.pair_count(a, b)
                item = QTableWidgetItem(str(value))
                if a != b and value > 0:
                    item.setBackground(QColor(80, 140, 220, min(40 + value * 40, 220)))
                self.matrix_table.setItem(r, c, item)

    def network_html(self) -> str:
        graph = build_graph(self.last_result, relations=self.rel_repo.relations(self.project_id))
        return to_html(graph)

    def _export_clicked(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        if self.last_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "ネットワーク HTML", "network.html", "HTML (*.html)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.network_html())

    # -- 関係定義 --------------------------------------------------------------
    def add_relation(self) -> None:
        a, b = self.rel_a.currentData(), self.rel_b.currentData()
        rel_type = self.rel_type.text().strip()
        if a is None or b is None or not rel_type or a == b:
            return
        self.rel_repo.add_relation(self.project_id, a, b, rel_type)
        self.rel_type.clear()
        self._refresh_relations()

    def _refresh_relations(self) -> None:
        self.rel_list.clear()
        names = {row["id"]: row["name"] for row in self._codes}
        for rel in self.rel_repo.relations(self.project_id):
            self.rel_list.addItem(
                f"{names.get(rel.code_a_id, rel.code_a_id)} —[{rel.relation_type}]→ "
                f"{names.get(rel.code_b_id, rel.code_b_id)}"
            )

    # -- ヒートマップ ----------------------------------------------------------
    def build_heatmap(self) -> None:
        ct = self.heat_repo.crosstab(self.project_id, self.dim_combo.currentData())
        self.heatmap_table.setRowCount(len(ct.row_codes))
        self.heatmap_table.setColumnCount(len(ct.columns))
        self.heatmap_table.setHorizontalHeaderLabels([str(c) for c in ct.columns])
        self.heatmap_table.setVerticalHeaderLabels([ct.code_names[c] for c in ct.row_codes])
        peak = max([ct.value(rc, col) for rc in ct.row_codes for col in ct.columns] + [1])
        for r, code in enumerate(ct.row_codes):
            for c, col in enumerate(ct.columns):
                v = ct.value(code, col)
                item = QTableWidgetItem(str(v))
                if v:
                    item.setBackground(QColor(220, 90, 60, int(40 + 180 * v / peak)))
                self.heatmap_table.setItem(r, c, item)
