"""共起・関係性可視化（3.6）のテスト（Qt 非依存）。"""

from __future__ import annotations

import json

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.modules.cooccurrence import (
    CooccurrenceRepository,
    HeatmapRepository,
    RelationRepository,
    build_graph,
    to_dict,
    to_html,
)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "co.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'A') RETURNING id", (pid,)
    ).fetchone()["id"]
    cb, cd = CodebookRepository(db), CodingRepository(db)
    yield db, pid, coder, cb, cd
    db.close()


def _doc(db, pid, body, *, year=None, author=None):
    row = db.conn.execute(
        "INSERT INTO document(project_id, title, body, year, author) VALUES (?, 'd', ?, ?, ?) "
        "RETURNING id",
        (pid, body, year, author),
    ).fetchone()
    db.conn.commit()
    return row["id"]


# -- 共起マトリクス -------------------------------------------------------------
def test_cooccurrence_overlap_scope(env):
    db, pid, coder, cb, cd = env
    did = _doc(db, pid, "0123456789")
    politics = cb.create_code(pid, "政治")
    person = cb.create_code(pid, "人物")
    event = cb.create_code(pid, "出来事")
    cd.add_coding(did, politics, coder, 0, 5)
    cd.add_coding(did, person, coder, 3, 8)        # 政治と重なる
    cd.add_coding(did, event, coder, 20, 25)       # 重ならない

    result = CooccurrenceRepository(db).matrix(pid, scope="overlap")
    assert result.pair_count(politics, person) == 1
    assert result.pair_count(politics, event) == 0
    assert result.frequencies[politics] == 1


def test_cooccurrence_distance_scope(env):
    db, pid, coder, cb, cd = env
    did = _doc(db, pid, "x" * 100)
    a = cb.create_code(pid, "A")
    b = cb.create_code(pid, "B")
    cd.add_coding(did, a, coder, 0, 10)
    cd.add_coding(did, b, coder, 20, 30)           # 間隔 10 文字

    repo = CooccurrenceRepository(db)
    assert repo.matrix(pid, scope="distance", distance=15).pair_count(a, b) == 1
    assert repo.matrix(pid, scope="distance", distance=5).pair_count(a, b) == 0


def test_cooccurrence_paragraph_scope(env):
    db, pid, coder, cb, cd = env
    body = "第一段落の本文です。\n\n第二段落は離れている。"
    did = _doc(db, pid, body)
    a = cb.create_code(pid, "A")
    b = cb.create_code(pid, "B")
    c = cb.create_code(pid, "C")
    cd.add_coding(did, a, coder, 0, 4)             # 第1段落
    cd.add_coding(did, b, coder, 5, 9)             # 第1段落
    p2 = body.index("第二段落")
    cd.add_coding(did, c, coder, p2, p2 + 4)       # 第2段落

    result = CooccurrenceRepository(db).matrix(pid, scope="paragraph")
    assert result.pair_count(a, b) == 1            # 同一段落
    assert result.pair_count(a, c) == 0            # 別段落


# -- ネットワーク ---------------------------------------------------------------
def test_build_graph_and_html_export(env):
    db, pid, coder, cb, cd = env
    did = _doc(db, pid, "0123456789")
    a = cb.create_code(pid, "政治")
    b = cb.create_code(pid, "人物")
    cd.add_coding(did, a, coder, 0, 5)
    cd.add_coding(did, b, coder, 3, 8)
    result = CooccurrenceRepository(db).matrix(pid, scope="overlap")

    rels = RelationRepository(db)
    rels.add_relation(pid, a, b, "対立", weight=2.0)

    graph = build_graph(result, relations=rels.relations(pid))
    assert {n.id for n in graph.nodes} == {a, b}
    # 共起エッジ＋意味的関係エッジ
    assert any(e.relation == "cooccurrence" for e in graph.edges)
    assert any(e.relation == "対立" for e in graph.edges)

    data = to_dict(graph)
    assert data["nodes"][0]["value"] >= 1
    html_text = to_html(graph)
    assert "vis-network" in html_text
    embedded = json.loads(html_text.split("const data = ", 1)[1].split(";\n", 1)[0])
    assert len(embedded["nodes"]) == 2


# -- 関係定義 -------------------------------------------------------------------
def test_relations_crud(env):
    db, pid, coder, cb, cd = env
    a = cb.create_code(pid, "A")
    b = cb.create_code(pid, "B")
    rels = RelationRepository(db)
    rid = rels.add_relation(pid, a, b, "因果")
    assert len(rels.relations(pid)) == 1
    assert rels.relations(pid, relation_type="因果")[0].relation_type == "因果"
    rels.remove_relation(rid)
    assert rels.relations(pid) == []


# -- ヒートマップ・時系列 -------------------------------------------------------
def test_heatmap_crosstab_by_year(env):
    db, pid, coder, cb, cd = env
    d1 = _doc(db, pid, "x" * 20, year=1867)
    d2 = _doc(db, pid, "y" * 20, year=1853)
    code = cb.create_code(pid, "政治")
    cd.add_coding(d1, code, coder, 0, 5)
    cd.add_coding(d1, code, coder, 6, 9)
    cd.add_coding(d2, code, coder, 0, 5)

    ct = HeatmapRepository(db).crosstab(pid, "year")
    assert ct.columns == [1853, 1867]
    assert ct.value(code, 1867) == 2
    assert ct.value(code, 1853) == 1


def test_timeseries_by_year(env):
    db, pid, coder, cb, cd = env
    d1 = _doc(db, pid, "x" * 20, year=1860)
    d2 = _doc(db, pid, "y" * 20, year=1868)
    code = cb.create_code(pid, "出来事")
    cd.add_coding(d1, code, coder, 0, 5)
    cd.add_coding(d2, code, coder, 0, 5)
    cd.add_coding(d2, code, coder, 6, 9)

    series = HeatmapRepository(db).timeseries(pid)
    assert series[code] == {1860: 1, 1868: 2}
