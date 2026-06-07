"""コーディング GUI（3.3）のテスト（offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QTextCursor

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "ui.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, '研究者A') RETURNING id", (pid,)
    ).fetchone()["id"]
    db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, '研究者B')", (pid,)
    )
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, 'doc', ?) RETURNING id",
        (pid, "朝廷は幕府に大政奉還を命じ徳川慶喜が応じた"),
    ).fetchone()["id"]
    db.conn.commit()
    yield db, pid, coder, did
    db.close()


# -- コードブックツリー ----------------------------------------------------------
def test_codebook_tree_shows_hierarchy_and_quick_keys(qapp, env):
    from shiryo_coder.ui.coding import CodebookTree

    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    p = cb.create_code(pid, "政治")
    cb.create_code(pid, "幕府", parent_id=p)

    tree = CodebookTree(cb, pid)
    assert tree.topLevelItemCount() == 1
    root = tree.topLevelItem(0)
    assert root.childCount() == 1
    assert "政治" in root.text(0)
    assert tree.quick_code(1) == p          # 数字キー 1 → 最初のコード
    tree.deleteLater()


def test_codebook_tree_reparent_and_cycle(qapp, env):
    from shiryo_coder.ui.coding import CodebookTree

    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    a = cb.create_code(pid, "A")
    b = cb.create_code(pid, "B", parent_id=a)

    tree = CodebookTree(cb, pid)
    assert tree.reparent(b, None) is True        # B を最上位へ
    assert tree.topLevelItemCount() == 2
    assert tree.reparent(a, b) is True           # A を B の下へ
    assert tree.reparent(b, a) is False          # 循環は拒否
    tree.deleteLater()


# -- コーディングビュー ----------------------------------------------------------
def test_coding_view_apply_and_visualize_overlap(qapp, env):
    from shiryo_coder.ui.coding import CodingView

    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    c1 = cb.create_code(pid, "出来事")
    c2 = cb.create_code(pid, "人物")
    body = db.conn.execute("SELECT body FROM document WHERE id=?", (did,)).fetchone()["body"]

    view = CodingView(cd)
    view.set_document(did, body, active_coder=coder)

    # 「大政奉還」を選択して付与
    i = body.index("大政奉還")
    cursor = view.textCursor()
    cursor.setPosition(i)
    cursor.setPosition(i + 4, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    sid = view.apply_code(c1)
    assert sid is not None
    assert view.visible_segment_count == 1

    # 部分重なりで別コードを付与 → 可視化は 2 セグメント
    j = body.index("奉還徳") if "奉還徳" in body else i + 2
    cursor.setPosition(j)
    cursor.setPosition(j + 4, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    view.apply_code(c2)
    assert view.visible_segment_count == 2
    assert len(cd.codings_at(did, i + 3)) >= 1
    view.deleteLater()


def test_coding_view_mode_switch(qapp, env):
    from shiryo_coder.ui.coding import CodingView
    from shiryo_coder.ui.coding.coding_view import MODE_HIGHLIGHT

    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    c1 = cb.create_code(pid, "X")
    cd.add_coding(did, c1, coder, 0, 4)

    view = CodingView(cd)
    body = db.conn.execute("SELECT body FROM document WHERE id=?", (did,)).fetchone()["body"]
    view.set_document(did, body, active_coder=coder)
    view.set_mode(MODE_HIGHLIGHT)
    # ハイライトモードでは背景色が設定される
    sel = view.extraSelections()[0]
    assert sel.format.background().color().alpha() > 0
    view.deleteLater()


# -- 統合ウィジェット（数字キー駆動・コーダー切替） -----------------------------
def test_coding_widget_quick_key_and_coder(qapp, env):
    from shiryo_coder.ui.coding import CodingWidget

    db, pid, coder, did = env
    cb = CodebookRepository(db)
    c1 = cb.create_code(pid, "人物")

    widget = CodingWidget(db, pid)
    widget.tree.reload()
    widget.open_document(did)

    # コーダーコンボに 2 名
    assert widget.coder_combo.count() == 2

    # 範囲選択して数字キー 1 → コード c1 を付与
    body = db.conn.execute("SELECT body FROM document WHERE id=?", (did,)).fetchone()["body"]
    i = body.index("徳川慶喜")
    cursor = widget.view.textCursor()
    cursor.setPosition(i)
    cursor.setPosition(i + 4, QTextCursor.MoveMode.KeepAnchor)
    widget.view.setTextCursor(cursor)

    sid = widget.apply_quick_code(1)
    assert sid is not None
    segs = CodingRepository(db).segments_for_document(did)
    assert len(segs) == 1
    assert segs[0].code_id == c1
    widget.deleteLater()
