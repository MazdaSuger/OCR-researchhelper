"""コーディング中核ロジック（3.3）のテスト（Qt 非依存）。"""

from __future__ import annotations

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import (
    CharNGramEmbedder,
    CodebookRepository,
    CodingRepository,
    CycleError,
    MemoRepository,
    assign_layers,
    auto_color,
    import_codebook,
    parse_codebook_xml,
    suggest_codes,
)
from shiryo_coder.modules.coding.coding import CodedSegment


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'me') RETURNING id", (pid,)
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, 'doc', ?) RETURNING id",
        (pid, "朝廷は幕府に大政奉還を命じ徳川慶喜が応じた"),
    ).fetchone()["id"]
    db.conn.commit()
    yield db, pid, coder, did
    db.close()


# -- 配色 -----------------------------------------------------------------------
def test_auto_color_distinct_and_valid():
    colors = [auto_color(i) for i in range(5)]
    assert all(c.startswith("#") and len(c) == 7 for c in colors)
    assert len(set(colors)) == 5


# -- コードブック階層 -----------------------------------------------------------
def test_codebook_hierarchy_and_autocolor(env):
    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    politics = cb.create_code(pid, "政治")
    bakufu = cb.create_code(pid, "幕府", parent_id=politics)
    cb.create_code(pid, "朝廷", parent_id=politics)

    roots = cb.tree(pid)
    assert len(roots) == 1
    assert roots[0].name == "政治"
    assert [c.name for c in roots[0].children] == ["幕府", "朝廷"]
    # 自動配色が付与される
    assert roots[0].color and roots[0].color.startswith("#")
    assert bakufu in {n.id for n in roots[0].walk()}


def test_codebook_move_and_cycle_guard(env):
    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    a = cb.create_code(pid, "A")
    b = cb.create_code(pid, "B", parent_id=a)
    c = cb.create_code(pid, "C", parent_id=b)

    # C を最上位へ移動
    cb.move_code(c, None)
    assert any(n.name == "C" for n in cb.tree(pid))

    # A を自身の子孫 B の下へ移動 → 循環で拒否
    cb.move_code(b, a)  # 戻す
    with pytest.raises(CycleError):
        cb.move_code(a, b)


def test_codebook_delete_cascades_children(env):
    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    parent = cb.create_code(pid, "親")
    cb.create_code(pid, "子", parent_id=parent)
    cb.delete_code(parent)
    assert cb.tree(pid) == []


# -- コーディング（重なり許容・レイヤー） ---------------------------------------
def test_coding_allows_overlap_and_multiple_codes_per_char(env):
    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    c1 = cb.create_code(pid, "出来事")
    c2 = cb.create_code(pid, "人物")

    cd.add_coding(did, c1, coder, 0, 10)
    cd.add_coding(did, c2, coder, 5, 15)        # 部分重なり

    at7 = cd.codings_at(did, 7)                 # 1 文字に 2 コード
    assert {s.code_id for s in at7} == {c1, c2}
    assert len(cd.segments_for_document(did)) == 2


def test_coding_dedupes_identical(env):
    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    c1 = cb.create_code(pid, "X")
    s1 = cd.add_coding(did, c1, coder, 0, 4)
    s2 = cd.add_coding(did, c1, coder, 0, 4)    # 同一 → 同じ id
    assert s1 == s2
    assert len(cd.segments_for_document(did)) == 1


def test_coding_status_workflow(env):
    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    c1 = cb.create_code(pid, "X")
    sid = cd.add_coding(did, c1, coder, 0, 4)
    cd.set_status(sid, "confirmed")
    assert cd.segments_for_document(did)[0].status == "confirmed"


def _seg(id_, start, end):
    return CodedSegment(id_, 1, 1, 1, start, end, "draft", "c", "#fff")


def test_assign_layers_separates_overlaps():
    segs = [_seg(1, 0, 10), _seg(2, 5, 15), _seg(3, 12, 20), _seg(4, 30, 40)]
    layers = assign_layers(segs)
    # 1 と 2 は重なる → 別レイヤー
    assert layers[1] != layers[2]
    # 1 と 3 は重ならない → 同レイヤーを再利用できる
    assert layers[1] == layers[3]
    # 全体で 2 レイヤーに収まり、離れた 4 は既存レイヤーを再利用（新規を作らない）
    assert max(layers.values()) == 1
    assert layers[4] in (0, 1)


# -- メモ 3 階層・ジャーナル ----------------------------------------------------
def test_memo_three_levels_and_journal(env):
    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "X")
    sid = cd.add_coding(did, code, coder, 0, 4)
    mr = MemoRepository(db)

    mr.add("プロジェクト方針", project_id=pid, coder_id=coder)
    mr.add("文書メモ", document_id=did, coder_id=coder)
    mr.add("セグメント注釈", segment_id=sid, coder_id=coder)
    mr.add("2026-06-07 分析ログ", project_id=pid, coder_id=coder, is_journal=True)

    assert len(mr.for_project(pid)) == 1
    assert len(mr.for_document(did)) == 1
    assert mr.for_segment(sid)[0].content == "セグメント注釈"
    assert len(mr.journal(pid)) == 1


# -- コードブック XML 取り込み（REFI-QDA） -------------------------------------
_QDC = """<?xml version="1.0" encoding="utf-8"?>
<CodeBook xmlns="urn:QDA-XML:codebook:1.0">
  <Codes>
    <Code guid="g1" name="政治" isCodable="true" color="#FF0000">
      <Description>政治に関する記述</Description>
      <Code guid="g2" name="幕府" isCodable="true" color="#00FF00"/>
      <Code guid="g3" name="朝廷" isCodable="true"/>
    </Code>
    <Code guid="g4" name="人物" isCodable="true"/>
  </Codes>
</CodeBook>
"""


def test_parse_codebook_xml_nested():
    roots = parse_codebook_xml(_QDC)
    assert [r.name for r in roots] == ["政治", "人物"]
    assert roots[0].color == "#FF0000"
    assert roots[0].definition == "政治に関する記述"
    assert [c.name for c in roots[0].children] == ["幕府", "朝廷"]


def test_import_codebook_into_repo(env):
    db, pid, _coder, _did = env
    cb = CodebookRepository(db)
    n = import_codebook(cb, pid, _QDC)
    assert n == 4
    roots = cb.tree(pid)
    assert [r.name for r in roots] == ["政治", "人物"]
    assert roots[0].children[0].name == "幕府"
    assert roots[0].children[0].color == "#00FF00"


# -- AI 支援コーディング --------------------------------------------------------
def test_ngram_embedder_and_suggest():
    examples = {
        1: ["徳川慶喜", "徳川家康"],     # 人物
        2: ["大政奉還", "王政復古"],     # 出来事
    }
    # 「徳川慶喜が」は人物コード(1)に最も近いはず
    suggestions = suggest_codes("徳川慶喜が", examples, embedder=CharNGramEmbedder(2))
    assert suggestions
    assert suggestions[0].code_id == 1
    assert suggestions[0].score > 0


def test_suggest_uses_real_coded_segments(env):
    db, pid, coder, did = env
    cb, cd = CodebookRepository(db), CodingRepository(db)
    person = cb.create_code(pid, "人物")
    event = cb.create_code(pid, "出来事")
    # body: 朝廷は幕府に大政奉還を命じ徳川慶喜が応じた
    body = db.conn.execute("SELECT body FROM document WHERE id=?", (did,)).fetchone()["body"]
    i = body.index("徳川慶喜")
    cd.add_coding(did, person, coder, i, i + 4)
    j = body.index("大政奉還")
    cd.add_coding(did, event, coder, j, j + 4)

    examples = cd.representative_texts(pid)
    assert set(examples) == {person, event}
    suggestions = suggest_codes("徳川家康", examples)
    assert suggestions[0].code_id == person
