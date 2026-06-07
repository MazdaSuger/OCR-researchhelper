"""エクスポート GUI（3.8）のテスト（offscreen）。"""

from __future__ import annotations

import os
import zipfile

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
    db = Database(tmp_path / "e.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('幕末研究') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'A') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body, year) VALUES (?, '史料A', ?, 1867) RETURNING id",
        (pid, "朝廷は幕府に大政奉還を命じた"),
    ).fetchone()["id"]
    db.conn.commit()
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "政治")
    cd.add_coding(did, code, coder, 0, 6)
    yield db, pid, did
    db.close()


def test_export_panel_csv_and_qdpx(qapp, seeded, tmp_path):
    from shiryo_coder.ui.export import ExportPanel

    db, pid, did = seeded
    panel = ExportPanel(db, pid)

    csv_path = panel.write_csv("segments", tmp_path / "seg.csv")
    assert "政治" in csv_path.read_text(encoding="utf-8-sig")

    qdpx = panel.write_qdpx(tmp_path / "p.qdpx")
    with zipfile.ZipFile(qdpx) as zf:
        assert "project.qde" in zf.namelist()
    panel.deleteLater()


def test_export_panel_vault_html_svg(qapp, seeded, tmp_path):
    from shiryo_coder.ui.export import ExportPanel

    db, pid, did = seeded
    panel = ExportPanel(db, pid)

    files = panel.write_vault(tmp_path / "vault")
    assert files and (tmp_path / "vault" / "史料A.md").exists()

    html = panel.write_html(tmp_path / "r.html")
    assert "<html" in html.read_text(encoding="utf-8")

    svg = panel.write_heatmap_svg(tmp_path / "h.svg", "year")
    assert svg.read_text(encoding="utf-8").startswith("<svg")
    panel.deleteLater()
