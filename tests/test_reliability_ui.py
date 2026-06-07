"""信頼性検証 GUI（3.5）のテスト（offscreen）。"""

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
    db = Database(tmp_path / "rel.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    a = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'A') RETURNING id", (pid,)
    ).fetchone()["id"]
    b = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'B') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, 'doc', '0123456789') RETURNING id",
        (pid,),
    ).fetchone()["id"]
    db.conn.commit()
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "X")
    cd.add_coding(did, code, a, 0, 6)
    cd.add_coding(did, code, b, 0, 4)
    yield db, pid, a, b, did, code
    db.close()


def test_panel_populates_controls(qapp, seeded):
    from shiryo_coder.ui.reliability import ReliabilityPanel

    db, pid, a, b, did, code = seeded
    panel = ReliabilityPanel(db, pid)
    assert panel.doc_combo.count() == 1
    assert panel.code_combo.count() == 1
    assert panel.coder_list.count() == 2
    panel.deleteLater()


def test_panel_computes_cohen_and_disagreements(qapp, seeded):
    from shiryo_coder.ui.reliability import ReliabilityPanel

    db, pid, a, b, did, code = seeded
    panel = ReliabilityPanel(db, pid)
    panel.check_coders([a, b])
    panel.compute()

    assert panel.last_result is not None
    assert panel.last_result.method == "cohen"
    # 4–6 が不一致 → 表に行があり、CSV 出力が有効
    assert panel.last_disagreements
    assert panel.table.rowCount() == len(panel.last_disagreements)
    assert panel.export_btn.isEnabled()
    csv_text = panel.disagreement_csv()
    assert csv_text.splitlines()[0].startswith("start,end,text")
    panel.deleteLater()


def test_panel_training_mode(qapp, seeded):
    from shiryo_coder.ui.reliability import ReliabilityPanel

    db, pid, a, b, did, code = seeded
    panel = ReliabilityPanel(db, pid)
    panel.check_coders([a, b])
    panel.training_check.setChecked(True)
    # 文字単位で見落とし/過剰を検出
    panel.gran_combo.setCurrentIndex(0)
    panel.compute()
    assert "研修フィードバック" in panel.result_label.text()
    panel.deleteLater()
