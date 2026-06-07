"""ライブラリ管理 GUI（3.2）のテスト（offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from shiryo_coder.db import Database
from shiryo_coder.modules.library import LibraryRepository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def seeded(tmp_path):
    db = Database(tmp_path / "ui.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    docs = [
        ("大政奉還", "朕惟フニ我皇祖皇宗", "徳川慶喜", 1867, "ja"),
        ("黒船来航", "ペリー提督の来航", "勝海舟", 1853, "ja"),
        ("Treaty", "Treaty of Kanagawa 1854", "Perry", 1854, "en"),
    ]
    for title, body, author, year, lang in docs:
        db.conn.execute(
            "INSERT INTO document(project_id, title, body, author, year, language) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, title, body, author, year, lang),
        )
    db.conn.commit()
    yield db, pid
    db.close()


def test_panel_lists_all_documents(qapp, seeded):
    from shiryo_coder.ui.library import LibraryPanel

    db, pid = seeded
    panel = LibraryPanel(LibraryRepository(db), pid)
    assert panel.row_count == 3
    # 言語フィルタの選択肢が読み込まれている
    langs = [panel.lang_combo.itemData(i) for i in range(panel.lang_combo.count())]
    assert set(langs) == {None, "ja", "en"}
    panel.deleteLater()


def test_panel_full_text_search(qapp, seeded):
    from shiryo_coder.ui.library import LibraryPanel

    db, pid = seeded
    panel = LibraryPanel(LibraryRepository(db), pid)
    panel.search_edit.setText("皇祖")
    panel.refresh()
    assert panel.row_count == 1
    assert panel.table.item(0, 0).text() == "大政奉還"

    panel.search_edit.setText("Kanagawa")
    panel.refresh()
    assert panel.row_count == 1
    assert panel.table.item(0, 0).text() == "Treaty"
    panel.deleteLater()


def test_panel_language_filter_and_sort(qapp, seeded):
    from shiryo_coder.ui.library import LibraryPanel

    db, pid = seeded
    panel = LibraryPanel(LibraryRepository(db), pid)

    # 言語フィルタ ja
    idx = panel.lang_combo.findData("ja")
    panel.lang_combo.setCurrentIndex(idx)
    assert panel.row_count == 2

    # 「年」列ヘッダクリックで昇順ソート（ja の 2 件: 1853, 1867）
    panel.lang_combo.setCurrentIndex(0)             # すべて
    panel._on_header_clicked(2)                     # 年で昇順
    years = [panel.table.item(r, 2).text() for r in range(panel.row_count)]
    assert years == ["1853", "1854", "1867"]
    panel._on_header_clicked(2)                     # 再クリックで降順
    years_desc = [panel.table.item(r, 2).text() for r in range(panel.row_count)]
    assert years_desc == ["1867", "1854", "1853"]
    panel.deleteLater()


def test_panel_preview_on_selection(qapp, seeded):
    from shiryo_coder.ui.library import LibraryPanel

    db, pid = seeded
    panel = LibraryPanel(LibraryRepository(db), pid)
    panel.table.setCurrentCell(0, 0)
    qapp.processEvents()
    assert panel.preview.toPlainText() != ""
    panel.deleteLater()


def test_main_window_collection_tree_filters(qapp, seeded):
    from shiryo_coder.ui.main_window import MainWindow

    db, pid = seeded
    repo = LibraryRepository(db)
    d1 = db.conn.execute("SELECT id FROM document ORDER BY id LIMIT 1").fetchone()["id"]
    col = repo.create_collection(pid, "幕末コレクション")
    repo.add_to_collection(d1, col)

    window = MainWindow(db)
    assert window.panel.row_count == 3              # 既定は全件

    # ツリーでコレクションを選択 → 1 件に絞り込み
    root = window.tree.topLevelItem(0)
    col_item = root.child(0)
    window.tree.setCurrentItem(col_item)
    qapp.processEvents()
    assert window.panel.row_count == 1
    window.deleteLater()
