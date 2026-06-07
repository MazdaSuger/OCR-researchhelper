"""HTML 静的レポート（仕様書 3.8）。

コード階層・代表例・統計（頻度・文書数・コーダー）をまとめた自己完結 HTML。
"""

from __future__ import annotations

import html
from pathlib import Path

from shiryo_coder.modules.coding import CodebookRepository, CodingRepository

_CSS = """
body{font-family:sans-serif;margin:2rem;line-height:1.6;color:#222}
h1{border-bottom:2px solid #444}
.code{margin:.2rem 0}
.swatch{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle}
.freq{color:#666;font-size:.9em}
.example{color:#444;background:#f6f6f6;padding:.2rem .5rem;border-left:3px solid #ccc;margin:.2rem 0}
table{border-collapse:collapse;margin:1rem 0}
td,th{border:1px solid #ddd;padding:.3rem .6rem}
"""


def build_report(db, project_id: int) -> str:
    """プロジェクトの HTML レポートを生成する。"""
    project = db.conn.execute(
        "SELECT name FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    name = html.escape(project["name"] if project else "プロジェクト")

    cb = CodebookRepository(db)
    cd = CodingRepository(db)
    freqs = cd.code_frequencies(project_id)
    examples = cd.representative_texts(project_id)

    doc_count = db.conn.execute(
        "SELECT COUNT(*) c FROM document WHERE project_id = ?", (project_id,)
    ).fetchone()["c"]
    seg_count = db.conn.execute(
        "SELECT COUNT(*) c FROM segment s JOIN document d ON d.id = s.document_id "
        "WHERE d.project_id = ?", (project_id,)
    ).fetchone()["c"]
    coders = db.conn.execute(
        "SELECT name, role FROM coder WHERE project_id = ? ORDER BY id", (project_id,)
    ).fetchall()

    def render(nodes, depth=0):
        out = []
        for node in nodes:
            freq = freqs.get(node.id, 0)
            swatch = (
                f'<span class="swatch" style="background:{html.escape(node.color)}"></span> '
                if node.color else ""
            )
            out.append(
                f'<div class="code" style="margin-left:{depth * 1.2}rem">'
                f'{swatch}<b>{html.escape(node.name)}</b> '
                f'<span class="freq">({freq})</span></div>'
            )
            ex = examples.get(node.id)
            if ex:
                out.append(f'<div class="example" style="margin-left:{depth * 1.2 + 1}rem">'
                           f'{html.escape(ex[0][:80])}</div>')
            out.append("".join(render(node.children, depth + 1)))
        return out

    coder_rows = "".join(
        f"<tr><td>{html.escape(c['name'])}</td><td>{html.escape(c['role'])}</td></tr>"
        for c in coders
    )

    return (
        "<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>"
        f"<title>{name} レポート</title><style>{_CSS}</style></head><body>"
        f"<h1>{name}</h1>"
        f"<p>文書 {doc_count} 件 / コーディング {seg_count} 件 / コーダー {len(coders)} 名</p>"
        "<h2>コードブック</h2>"
        f"{''.join(render(cb.tree(project_id)))}"
        "<h2>コーダー</h2>"
        f"<table><tr><th>名前</th><th>役割</th></tr>{coder_rows}</table>"
        "</body></html>"
    )


def write_report(db, project_id: int, path: Path | str) -> Path:
    path = Path(path)
    path.write_text(build_report(db, project_id), encoding="utf-8")
    return path
