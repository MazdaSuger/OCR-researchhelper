"""エクスポート・連携（3.8）のテスト（Qt 非依存）。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.modules.cooccurrence import CooccurrenceRepository, HeatmapRepository
from shiryo_coder.modules.export import (
    build_report,
    export_qdpx,
    export_vault,
    format_citation,
    format_segment_citation,
    heatmap_svg,
    timeseries_svg,
    to_csv,
)
from shiryo_coder.modules.export.tables import excel_available, to_excel

_NS = "urn:QDA-XML:project:1.0"


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "e.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('幕末研究') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name, role) VALUES (?, '主任', 'admin') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body, author, year) "
        "VALUES (?, '大政奉還上表文', ?, '徳川慶喜', 1867) RETURNING id",
        (pid, "朝廷は幕府に大政奉還を命じ徳川慶喜が応じた"),
    ).fetchone()["id"]
    db.conn.commit()
    cb, cd = CodebookRepository(db), CodingRepository(db)
    politics = cb.create_code(pid, "政治")
    person = cb.create_code(pid, "人物", parent_id=politics)
    body = "朝廷は幕府に大政奉還を命じ徳川慶喜が応じた"
    cd.add_coding(did, politics, coder, 0, 6)
    i = body.index("徳川慶喜")
    sid = cd.add_coding(did, person, coder, i, i + 4)
    yield db, pid, coder, did, politics, person, sid
    db.close()


# -- CSV / Excel ----------------------------------------------------------------
def test_csv_tables(env):
    db, pid, coder, did, politics, person, sid = env
    codes = to_csv(db, pid, "codes")
    assert codes.splitlines()[0] == "code_id,name,frequency,documents"
    assert "政治" in codes

    segs = to_csv(db, pid, "segments")
    assert "大政奉還上表文" in segs and "徳川慶喜" in segs

    meta = to_csv(db, pid, "metadata")
    assert "徳川慶喜" in meta and "1867" in meta


@pytest.mark.skipif(not excel_available(), reason="openpyxl が必要")
def test_excel_export(env, tmp_path):
    db, pid, *_ = env
    path = to_excel(db, pid, tmp_path / "out.xlsx")
    import openpyxl

    wb = openpyxl.load_workbook(path)
    assert set(wb.sheetnames) == {"codes", "segments", "metadata", "sentiment"}


# -- 引用形式 -------------------------------------------------------------------
def test_citation_styles():
    doc = {"author": "徳川慶喜", "title": "大政奉還上表文", "year": 1867, "source": "幕末史料集"}
    apa = format_citation(doc, "apa")
    assert "徳川慶喜 (1867)" in apa and "大政奉還上表文" in apa

    chicago = format_citation(doc, "chicago")
    assert '"大政奉還上表文."' in chicago and "1867" in chicago

    sist = format_citation(doc, "sist02")
    assert sist.startswith("徳川慶喜. 大政奉還上表文.")


def test_segment_citation(env):
    db, pid, coder, did, politics, person, sid = env
    cite = format_segment_citation(db, sid, "sist02")
    assert "「徳川慶喜」" in cite and "1867" in cite


# -- REFI-QDA .qdpx -------------------------------------------------------------
def test_qdpx_export_is_valid(env, tmp_path):
    db, pid, coder, did, politics, person, sid = env
    path = export_qdpx(db, pid, tmp_path / "project.qdpx")

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert "project.qde" in names
        assert any(n.startswith("sources/") and n.endswith(".txt") for n in names)
        qde = zf.read("project.qde").decode("utf-8")
        # ソースの本文が同梱されている
        src_file = next(n for n in names if n.startswith("sources/"))
        assert "徳川慶喜" in zf.read(src_file).decode("utf-8")

    root = ET.fromstring(qde)
    codes = root.findall(f".//{{{_NS}}}Code")
    assert {c.get("name") for c in codes} == {"政治", "人物"}
    # 階層: 人物 は 政治 の子
    politics_el = next(c for c in codes if c.get("name") == "政治")
    assert politics_el.find(f"{{{_NS}}}Code").get("name") == "人物"
    # コーディングがコードを参照
    coderefs = root.findall(f".//{{{_NS}}}CodeRef")
    code_guids = {c.get("guid") for c in codes}
    assert coderefs and all(cr.get("targetGUID") in code_guids for cr in coderefs)
    # 選択範囲の位置
    sel = root.find(f".//{{{_NS}}}PlainTextSelection")
    assert sel.get("startPosition") is not None


# -- Obsidian Vault -------------------------------------------------------------
def test_obsidian_vault_export(env, tmp_path):
    db, pid, coder, did, politics, person, sid = env
    db.conn.execute(
        "INSERT INTO code_relation(project_id, code_a_id, code_b_id, relation_type) "
        "VALUES (?, ?, ?, '包含')",
        (pid, politics, person),
    )
    db.conn.commit()

    paths = export_vault(db, pid, tmp_path / "vault")
    md = (tmp_path / "vault" / "大政奉還上表文.md").read_text(encoding="utf-8")
    assert "tags:" in md and "政治" in md
    assert "> [!note]" in md and "[[政治]]" in md        # callout + wikilink
    rel = (tmp_path / "vault" / "コード関係.md").read_text(encoding="utf-8")
    assert "[[政治]]" in rel and "包含" in rel


# -- HTML レポート --------------------------------------------------------------
def test_html_report(env):
    db, pid, coder, did, politics, person, sid = env
    report = build_report(db, pid)
    assert "<html" in report and "幕末研究" in report
    assert "政治" in report and "人物" in report
    assert "主任" in report                              # コーダー表


# -- SVG 可視化 -----------------------------------------------------------------
def test_heatmap_and_timeseries_svg(env):
    db, pid, coder, did, politics, person, sid = env
    ct = HeatmapRepository(db).crosstab(pid, "year")
    svg = heatmap_svg(ct)
    assert svg.startswith("<svg") and "<rect" in svg and "1867" in svg

    ts = timeseries_svg({1860: -0.3, 1867: 0.5})
    assert "<polyline" in ts and "1867" in ts
