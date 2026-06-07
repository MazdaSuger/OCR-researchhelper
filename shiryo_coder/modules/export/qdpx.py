"""REFI-QDA .qdpx エクスポート（仕様書 3.8）。

MAXQDA / NVivo / ATLAS.ti / QualCoder 互換の交換形式。.qdpx は ZIP で、ルートに
`project.qde`（QDA-XML project 1.0）、`sources/` に各文書のプレーンテキストを含む。
コードは階層・色つき、コーディングは PlainTextSelection＋Coding（CodeRef/作成者）。
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_NS = "urn:QDA-XML:project:1.0"


def _guid() -> str:
    return str(uuid.uuid4())


def _build_qde(db, project_id: int) -> tuple[str, dict[int, str]]:
    """project.qde の XML 文字列と、source guid→本文 のマップを返す。"""
    ET.register_namespace("", _NS)
    project_row = db.conn.execute(
        "SELECT name FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    root = ET.Element(f"{{{_NS}}}Project", {
        "name": project_row["name"] if project_row else "project",
        "origin": "Shiryo-Coder",
    })

    # Users（コーダー）
    coder_guid: dict[int, str] = {}
    users = ET.SubElement(root, f"{{{_NS}}}Users")
    for r in db.conn.execute(
        "SELECT id, name FROM coder WHERE project_id = ? ORDER BY id", (project_id,)
    ):
        coder_guid[r["id"]] = _guid()
        ET.SubElement(users, f"{{{_NS}}}User", {"guid": coder_guid[r["id"]], "name": r["name"]})

    # CodeBook（階層）
    code_guid: dict[int, str] = {}
    codebook = ET.SubElement(root, f"{{{_NS}}}CodeBook")
    codes_el = ET.SubElement(codebook, f"{{{_NS}}}Codes")
    code_rows = db.conn.execute(
        "SELECT id, parent_id, name, color, definition FROM code WHERE project_id = ? "
        "ORDER BY sort_order, id",
        (project_id,),
    ).fetchall()
    for r in code_rows:
        code_guid[r["id"]] = _guid()
    children: dict[int | None, list] = {}
    for r in code_rows:
        children.setdefault(r["parent_id"], []).append(r)

    def add_codes(parent_el, parent_id):
        for r in children.get(parent_id, []):
            attrs = {"guid": code_guid[r["id"]], "name": r["name"], "isCodable": "true"}
            if r["color"]:
                attrs["color"] = r["color"]
            el = ET.SubElement(parent_el, f"{{{_NS}}}Code", attrs)
            if r["definition"]:
                ET.SubElement(el, f"{{{_NS}}}Description").text = r["definition"]
            add_codes(el, r["id"])

    add_codes(codes_el, None)

    # Sources（各文書 = TextSource、コーディングを内包）
    bodies: dict[str, str] = {}
    sources = ET.SubElement(root, f"{{{_NS}}}Sources")
    for d in db.conn.execute(
        "SELECT id, title, body FROM document WHERE project_id = ? ORDER BY id", (project_id,)
    ):
        src_guid = _guid()
        bodies[src_guid] = d["body"]
        ts = ET.SubElement(sources, f"{{{_NS}}}TextSource", {
            "guid": src_guid, "name": d["title"],
            "plainTextPath": f"internal://{src_guid}.txt",
        })
        for s in db.conn.execute(
            "SELECT id, code_id, coder_id, char_start, char_end FROM segment "
            "WHERE document_id = ? ORDER BY char_start",
            (d["id"],),
        ):
            sel = ET.SubElement(ts, f"{{{_NS}}}PlainTextSelection", {
                "guid": _guid(),
                "startPosition": str(s["char_start"]),
                "endPosition": str(s["char_end"]),
            })
            coding_attrs = {"guid": _guid()}
            if s["coder_id"] in coder_guid:
                coding_attrs["creatingUser"] = coder_guid[s["coder_id"]]
            coding = ET.SubElement(sel, f"{{{_NS}}}Coding", coding_attrs)
            ET.SubElement(coding, f"{{{_NS}}}CodeRef", {"targetGUID": code_guid[s["code_id"]]})

    xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return xml, bodies


def export_qdpx(db, project_id: int, path: Path | str) -> Path:
    """プロジェクトを .qdpx（ZIP）として書き出す。"""
    path = Path(path)
    qde_xml, bodies = _build_qde(db, project_id)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.qde", qde_xml)
        for src_guid, body in bodies.items():
            zf.writestr(f"sources/{src_guid}.txt", body)
    return path
