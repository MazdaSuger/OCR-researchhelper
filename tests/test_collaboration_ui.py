"""共同作業 GUI（3.7）のテスト（offscreen）。"""

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
    admin = db.conn.execute(
        "INSERT INTO coder(project_id, name, role) VALUES (?, '主任', 'admin') RETURNING id", (pid,)
    ).fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name, role) VALUES (?, '院生', 'coder') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, '史料A', '0123456789') RETURNING id",
        (pid,),
    ).fetchone()["id"]
    db.conn.commit()
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "政治")
    sid = cd.add_coding(did, code, coder, 0, 5)
    yield db, pid, admin, coder, did, sid
    db.close()


def test_panel_lists_accounts_and_users(qapp, seeded):
    from shiryo_coder.ui.collaboration import CollaborationPanel

    db, pid, admin, coder, did, sid = seeded
    panel = CollaborationPanel(db, pid)
    assert panel.account_table.rowCount() == 2
    assert panel.user_combo.count() == 2
    panel.deleteLater()


def test_panel_add_account_and_change_role(qapp, seeded):
    from shiryo_coder.ui.collaboration import CollaborationPanel

    db, pid, admin, coder, did, sid = seeded
    panel = CollaborationPanel(db, pid)
    panel.name_edit.setText("閲覧者")
    panel.role_combo.setCurrentText("viewer")
    panel.add_account()
    assert panel.account_table.rowCount() == 3
    panel.deleteLater()


def test_panel_approval_flow_as_admin(qapp, seeded):
    from shiryo_coder.ui.collaboration import CollaborationPanel

    db, pid, admin, coder, did, sid = seeded
    panel = CollaborationPanel(db, pid)
    # 操作ユーザーを主任(admin)に
    panel.user_combo.setCurrentIndex(panel.user_combo.findData(admin))
    assert panel.draft_list.count() == 1
    panel.draft_list.setCurrentRow(0)
    panel.approve_selected()
    assert panel.draft_list.count() == 0
    assert panel.reviewed_list.count() == 1
    panel.reviewed_list.setCurrentRow(0)
    panel.confirm_selected()
    assert panel.reviewed_list.count() == 0
    # 履歴に承認・確定が出る
    actions = {
        panel.history_table.item(r, 3).text() for r in range(panel.history_table.rowCount())
    }
    assert {"approve", "confirm"} <= actions
    panel.deleteLater()


def test_panel_locking(qapp, seeded):
    from shiryo_coder.ui.collaboration import CollaborationPanel

    db, pid, admin, coder, did, sid = seeded
    panel = CollaborationPanel(db, pid)
    panel.user_combo.setCurrentIndex(panel.user_combo.findData(coder))
    panel.acquire_lock()
    assert panel.lock_list.count() == 1
    panel.release_lock()
    assert panel.lock_list.count() == 0
    panel.deleteLater()
