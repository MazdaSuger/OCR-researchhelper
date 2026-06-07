"""センチメント分析 GUI（3.4）のテスト（offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from shiryo_coder.db import Database


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def seeded(tmp_path):
    db = Database(tmp_path / "s.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    db.conn.execute(
        "INSERT INTO document(project_id, title, body, year) VALUES (?, 'doc', ?, 1867)",
        (pid, "勝利の喜び。逆賊の罪。"),
    )
    db.conn.commit()
    yield db, pid
    db.close()


def test_panel_analyze_by_sentence(qapp, seeded):
    from shiryo_coder.ui.sentiment import SentimentPanel

    db, pid = seeded
    panel = SentimentPanel(db, pid)
    panel.unit_combo.setCurrentIndex(0)            # 文
    panel.analyze()
    assert panel.result_table.rowCount() == 2
    panel.deleteLater()


def test_panel_timeseries(qapp, seeded):
    from shiryo_coder.ui.sentiment import SentimentPanel

    db, pid = seeded
    panel = SentimentPanel(db, pid)
    panel.unit_combo.setCurrentIndex(3)            # 文書全体
    panel.analyze()
    panel.build_timeseries()
    assert panel.agg_table.rowCount() == 1         # 1867 のみ
    panel.deleteLater()


def test_panel_morphology_toggle(qapp, seeded):
    from shiryo_coder.ui.sentiment import SentimentPanel
    from shiryo_coder.modules.sentiment import sudachi_available

    db, pid = seeded
    panel = SentimentPanel(db, pid)
    if sudachi_available():
        assert panel.morph_check.isChecked()
        analyzer = panel._analyzer()
        assert analyzer.tokenizer is not None
    panel.morph_check.setChecked(False)
    assert panel._analyzer().tokenizer is None
    panel.deleteLater()


def test_panel_lexicon_editor(qapp, seeded):
    from shiryo_coder.ui.sentiment import SentimentPanel

    db, pid = seeded
    panel = SentimentPanel(db, pid)
    panel.word_edit.setText("我が君")
    panel.polarity_spin.setValue(0.8)
    panel.add_word()
    assert panel.lex_list.count() == 1
    # カスタム辞書を使った解析でカスタム語が効く
    panel.dict_combo.setCurrentIndex(2)            # 内蔵＋カスタム
    analyzer = panel._analyzer()
    assert analyzer.dictionary.polarity("我が君") == pytest.approx(0.8)
    panel.deleteLater()
