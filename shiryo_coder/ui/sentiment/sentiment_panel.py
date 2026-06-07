"""センチメント分析パネル（仕様書 3.4）。

文書・分析単位・辞書を選んで極性を計算し、年代別時系列とコード別の極性分布、
カスタム史料辞書の編集を提供する。
"""

from __future__ import annotations

from statistics import mean

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.sentiment import (
    SOURCES,
    LexiconRepository,
    SentimentAnalyzer,
    SentimentDictionary,
    SentimentRepository,
    installed,
    load_combined,
    load_external,
    spacy_available,
    sudachi_available,
)

_UNITS = [("文", "sentence"), ("段落", "paragraph"), ("セグメント", "segment"), ("文書全体", "document")]
_DICTS = [("内蔵（日本語）", "ja"), ("内蔵（英語）", "en"), ("内蔵＋カスタム（日本語）", "ja+custom")]


def _polarity_color(p: float) -> QColor:
    if p > 0:
        return QColor(70, 160, 90, int(40 + 180 * min(p, 1.0)))
    if p < 0:
        return QColor(200, 70, 60, int(40 + 180 * min(-p, 1.0)))
    return QColor(0, 0, 0, 0)


class SentimentPanel(QWidget):
    """解析・集計・辞書編集のタブ。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.repo = SentimentRepository(db)
        self.lexicon = LexiconRepository(db)

        tabs = QTabWidget()
        tabs.addTab(self._build_analyze_tab(), "解析")
        tabs.addTab(self._build_aggregate_tab(), "集計")
        tabs.addTab(self._build_lexicon_tab(), "辞書編集")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self.reload()

    # -- 解析タブ --------------------------------------------------------------
    def _build_analyze_tab(self) -> QWidget:
        self.doc_combo = QComboBox()
        self.unit_combo = QComboBox()
        for label, value in _UNITS:
            self.unit_combo.addItem(label, value)
        self.dict_combo = QComboBox()   # 内容は reload() で（外部辞書の導入状況を反映）

        self.morph_check = QCheckBox("形態素解析")
        morph_ok = sudachi_available() or spacy_available()
        self.morph_check.setEnabled(morph_ok)
        self.morph_check.setChecked(morph_ok)
        self.morph_check.setToolTip(
            "Sudachi(日)/spaCy(英) で活用語を辞書形に正規化して照合します。"
            if morph_ok else "形態素解析器が未導入です（pip install で有効化）"
        )

        analyze_btn = QPushButton("解析")
        analyze_btn.clicked.connect(self.analyze)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("史料"))
        controls.addWidget(self.doc_combo, 1)
        controls.addWidget(QLabel("単位"))
        controls.addWidget(self.unit_combo)
        controls.addWidget(QLabel("辞書"))
        controls.addWidget(self.dict_combo)
        controls.addWidget(self.morph_check)
        controls.addWidget(analyze_btn)

        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["範囲", "極性", "テキスト"])
        self.result_table.horizontalHeader().setStretchLastSection(True)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(controls)
        layout.addWidget(self.result_table, 1)
        return tab

    def _build_aggregate_tab(self) -> QWidget:
        ts_btn = QPushButton("年代別時系列（平均極性）")
        ts_btn.clicked.connect(self.build_timeseries)
        bc_btn = QPushButton("コード別の極性分布")
        bc_btn.clicked.connect(self.build_by_code)

        buttons = QHBoxLayout()
        buttons.addWidget(ts_btn)
        buttons.addWidget(bc_btn)
        buttons.addStretch(1)

        self.agg_table = QTableWidget(0, 0)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(buttons)
        layout.addWidget(self.agg_table, 1)
        return tab

    def _build_lexicon_tab(self) -> QWidget:
        self.word_edit = QLineEdit()
        self.word_edit.setPlaceholderText("語（例: 我が君）")
        self.polarity_spin = QDoubleSpinBox()
        self.polarity_spin.setRange(-1.0, 1.0)
        self.polarity_spin.setSingleStep(0.1)
        add_btn = QPushButton("辞書に追加/更新")
        add_btn.clicked.connect(self.add_word)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("カスタム史料辞書"))
        controls.addWidget(self.word_edit, 1)
        controls.addWidget(self.polarity_spin)
        controls.addWidget(add_btn)

        self.lex_list = QListWidget()

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(controls)
        layout.addWidget(self.lex_list, 1)
        return tab

    # -- データ読み込み ---------------------------------------------------------
    def reload(self) -> None:
        self.doc_combo.clear()
        for row in self.db.conn.execute(
            "SELECT id, title FROM document WHERE project_id = ? ORDER BY id",
            (self.project_id,),
        ):
            self.doc_combo.addItem(row["title"], row["id"])
        self._reload_dicts()
        self._refresh_lexicon()

    def _reload_dicts(self) -> None:
        current = self.dict_combo.currentData()
        self.dict_combo.blockSignals(True)
        self.dict_combo.clear()
        for label, value in _DICTS:
            self.dict_combo.addItem(label, value)
        ext = [k for k in installed() if SOURCES[k].language == "ja"]
        if ext:
            self.dict_combo.addItem("内蔵＋外部（導入済み・日本語）", "ja+external")
            for key in ext:
                self.dict_combo.addItem(SOURCES[key].name, f"ext:{key}")
        idx = self.dict_combo.findData(current)
        self.dict_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.dict_combo.blockSignals(False)

    def _analyzer(self) -> SentimentAnalyzer:
        choice = self.dict_combo.currentData()
        if choice == "en":
            dictionary = SentimentDictionary.builtin("en")
        elif choice == "ja+custom":
            dictionary = self.lexicon.merged_with_builtin(self.project_id, "ja")
        elif choice == "ja+external":
            # 内蔵＋導入済み外部辞書＋カスタム
            dictionary = load_combined("ja").merge(
                self.lexicon.to_dictionary(self.project_id, "ja")
            )
        elif isinstance(choice, str) and choice.startswith("ext:"):
            dictionary = load_external(choice[4:])
        else:
            dictionary = SentimentDictionary.builtin("ja")
        tokenizer = "auto" if self.morph_check.isChecked() else None
        return SentimentAnalyzer(dictionary, tokenizer=tokenizer)

    # -- 解析 ------------------------------------------------------------------
    def analyze(self) -> None:
        doc = self.doc_combo.currentData()
        if doc is None:
            return
        unit = self.unit_combo.currentData()
        results = self.repo.analyze_document(doc, self._analyzer(), unit=unit)
        self.result_table.setRowCount(len(results))
        for r, u in enumerate(results):
            rng = "全体" if u.char_start is None else f"{u.char_start}–{u.char_end}"
            self.result_table.setItem(r, 0, QTableWidgetItem(rng))
            pol = QTableWidgetItem(f"{u.polarity:+.2f}")
            pol.setBackground(_polarity_color(u.polarity))
            self.result_table.setItem(r, 1, pol)
            self.result_table.setItem(r, 2, QTableWidgetItem(u.text[:60]))

    # -- 集計 ------------------------------------------------------------------
    def build_timeseries(self) -> None:
        series = self.repo.timeseries(self.project_id, unit=self.unit_combo.currentData())
        years = sorted(series)
        self.agg_table.clear()
        self.agg_table.setColumnCount(2)
        self.agg_table.setHorizontalHeaderLabels(["年代", "平均極性"])
        self.agg_table.setRowCount(len(years))
        for r, y in enumerate(years):
            self.agg_table.setItem(r, 0, QTableWidgetItem(str(y)))
            item = QTableWidgetItem(f"{series[y]:+.3f}")
            item.setBackground(_polarity_color(series[y]))
            self.agg_table.setItem(r, 1, item)

    def build_by_code(self) -> None:
        by_code = self.repo.by_code(self.project_id)
        names = {
            row["id"]: row["name"]
            for row in self.db.conn.execute(
                "SELECT id, name FROM code WHERE project_id = ?", (self.project_id,)
            )
        }
        self.agg_table.clear()
        self.agg_table.setColumnCount(5)
        self.agg_table.setHorizontalHeaderLabels(["コード", "件数", "平均", "最小", "最大"])
        self.agg_table.setRowCount(len(by_code))
        for r, (cid, values) in enumerate(by_code.items()):
            self.agg_table.setItem(r, 0, QTableWidgetItem(names.get(cid, str(cid))))
            self.agg_table.setItem(r, 1, QTableWidgetItem(str(len(values))))
            self.agg_table.setItem(r, 2, QTableWidgetItem(f"{mean(values):+.3f}"))
            self.agg_table.setItem(r, 3, QTableWidgetItem(f"{min(values):+.3f}"))
            self.agg_table.setItem(r, 4, QTableWidgetItem(f"{max(values):+.3f}"))

    # -- 辞書編集 --------------------------------------------------------------
    def add_word(self) -> None:
        word = self.word_edit.text().strip()
        if not word:
            return
        self.lexicon.set_word(self.project_id, word, self.polarity_spin.value(), language="ja")
        self.word_edit.clear()
        self._refresh_lexicon()

    def _refresh_lexicon(self) -> None:
        self.lex_list.clear()
        for word, polarity in sorted(self.lexicon.words(self.project_id, language="ja").items()):
            self.lex_list.addItem(f"{word}: {polarity:+.2f}")
