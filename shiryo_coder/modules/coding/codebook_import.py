"""コードブック XML 取り込み（QualCoder / REFI-QDA .qdc）。仕様書 3.3。

REFI-QDA Codebook 形式（ネストした <Code> 要素、name/color 属性、<Description>）を
パースしてアプリのコードブックへ取り込む。名前空間の有無に依存しないよう局所名で判定。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CodeImport:
    """取り込み用の中間表現。"""

    name: str
    color: str | None = None
    definition: str | None = None
    children: list["CodeImport"] = field(default_factory=list)


def _local(tag: str) -> str:
    """`{ns}Tag` → `Tag`。"""
    return tag.rsplit("}", 1)[-1]


def _parse_code(element: ET.Element) -> CodeImport:
    name = element.get("name") or element.get("Name") or ""
    color = element.get("color") or element.get("Color")
    definition = None
    children: list[CodeImport] = []
    for child in element:
        local = _local(child.tag)
        if local == "Description":
            definition = (child.text or "").strip() or None
        elif local == "Code":
            children.append(_parse_code(child))
    return CodeImport(name=name, color=color, definition=definition, children=children)


def parse_codebook_xml(source: str | Path) -> list[CodeImport]:
    """XML 文字列またはファイルパスから最上位コードのリストを返す。"""
    text = source
    if isinstance(source, Path) or (
        isinstance(source, str) and "<" not in source and Path(source).exists()
    ):
        text = Path(source).read_text(encoding="utf-8")
    root = ET.fromstring(text)
    # <Codes> を探す（root が CodeBook でも Codes でも対応）
    codes_parent = root
    if _local(root.tag) != "Codes":
        found = next((e for e in root.iter() if _local(e.tag) == "Codes"), None)
        if found is not None:
            codes_parent = found
    return [
        _parse_code(child)
        for child in codes_parent
        if _local(child.tag) == "Code"
    ]


def import_codebook(repo, project_id: int, source: str | Path) -> int:
    """コードブックを取り込み、作成したコード数を返す。"""
    roots = parse_codebook_xml(source)
    count = 0

    def create(items: list[CodeImport], parent_id: int | None) -> None:
        nonlocal count
        for item in items:
            code_id = repo.create_code(
                project_id, item.name,
                parent_id=parent_id, definition=item.definition, color=item.color,
            )
            count += 1
            create(item.children, code_id)

    create(roots, None)
    return count
