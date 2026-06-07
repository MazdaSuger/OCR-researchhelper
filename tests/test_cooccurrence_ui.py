"""共起・関係性可視化 GUI（3.6）のテスト（offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def seeded(tmp_path):
    db = Database(tmp_path / "co.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'A') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body, year, author) "
        "VALUES (?, 'd', ?, 1867, '徳川') RETURNING id",
        (pid, "0123456789"),
    ).fetchone()["id"]
    db.conn.commit()
    cb, cd = CodebookRepository(db), CodingRepository(db)
    politics = cb.create_code(pid, "政治")
    person = cb.create_code(pid, "人物")
    cd.add_coding(did, politics, coder, 0, 5)
    cd.add_coding(did, person, coder, 3, 8)
    yield db, pid, politics, person, did
    db.close()


def test_panel_computes_matrix_and_enables_export(qapp, seeded):
    from shiryo_coder.ui.cooccurrence import CooccurrencePanel

    db, pid, politics, person, did = seeded
    panel = CooccurrencePanel(db, pid)
    panel.compute_matrix()
    assert panel.matrix_table.rowCount() == 2
    assert panel.matrix_table.columnCount() == 2
    assert panel.export_btn.isEnabled()

    # ネットワーク HTML が生成できる
    html_text = panel.network_html()
    assert "vis-network" in html_text
    panel.deleteLater()


def test_panel_add_relation(qapp, seeded):
    from shiryo_coder.ui.cooccurrence import CooccurrencePanel

    db, pid, politics, person, did = seeded
    panel = CooccurrencePanel(db, pid)
    panel.rel_a.setCurrentIndex(0)
    panel.rel_b.setCurrentIndex(1)
    panel.rel_type.setText("対立")
    panel.add_relation()
    assert panel.rel_list.count() == 1
    panel.deleteLater()


def test_panel_heatmap_by_year(qapp, seeded):
    from shiryo_coder.ui.cooccurrence import CooccurrencePanel

    db, pid, politics, person, did = seeded
    panel = CooccurrencePanel(db, pid)
    panel.dim_combo.setCurrentIndex(0)             # 年代
    panel.build_heatmap()
    assert panel.heatmap_table.columnCount() == 1  # 1867 のみ
    assert panel.heatmap_table.rowCount() == 2
    panel.deleteLater()
