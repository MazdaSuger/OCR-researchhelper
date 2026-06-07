"""ライブラリ管理 / FTS 検索（3.2）のテスト。"""

from __future__ import annotations

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.library import LibraryRepository
from shiryo_coder.modules.library import obsidian, zotero


@pytest.fixture
def repo(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.initialize()
    pid = db.conn.execute(
        "INSERT INTO project(name) VALUES ('p') RETURNING id"
    ).fetchone()["id"]
    yield LibraryRepository(db), db, pid
    db.close()


def _add(db, project_id, *, title, body, **cols):
    keys = ["project_id", "title", "body", *cols.keys()]
    vals = [project_id, title, body, *cols.values()]
    ph = ", ".join("?" for _ in keys)
    row = db.conn.execute(
        f"INSERT INTO document({', '.join(keys)}) VALUES ({ph}) RETURNING id", vals
    ).fetchone()
    db.conn.commit()
    return row["id"]


# -- 言語別 FTS ------------------------------------------------------------------
def test_fts_japanese_routes_to_trigram(repo):
    r, db, pid = repo
    jid = _add(db, pid, title="大政奉還", body="朕惟フニ我皇祖皇宗國ヲ肇ムルコト", language="ja")
    # trigram 索引にあり、横断検索で部分文字列がヒットする
    assert db.conn.execute(
        "SELECT count(*) c FROM document_fts_tri WHERE document_fts_tri MATCH ?",
        ('"皇祖皇宗"',),
    ).fetchone()["c"] == 1
    assert [d.id for d in r.search("皇祖皇宗")] == [jid]


def test_fts_english_routes_to_unicode61(repo):
    r, db, pid = repo
    eid = _add(db, pid, title="Restoration", body="The Meiji Restoration of 1868", language="en")
    assert db.conn.execute(
        "SELECT count(*) c FROM document_fts_uni WHERE document_fts_uni MATCH 'meiji'"
    ).fetchone()["c"] == 1
    # 大文字小文字・部分一致（unicode61 は語単位）
    assert [d.id for d in r.search("Meiji")] == [eid]


def test_fts_cross_language_search(repo):
    r, db, pid = repo
    _add(db, pid, title="和", body="徳川慶喜", language="ja")
    _add(db, pid, title="En", body="Tokugawa Yoshinobu", language="en")
    assert len(r.search("徳川")) == 1
    assert len(r.search("Tokugawa")) == 1


def test_fts_updates_on_language_change(repo):
    r, db, pid = repo
    did = _add(db, pid, title="t", body="alpha beta", language="en")
    assert len(r.search("beta")) == 1
    # 言語を ja に変更 → trigram へ移動、unicode61 からは消える
    db.conn.execute("UPDATE document SET language='ja' WHERE id=?", (did,))
    db.conn.commit()
    assert db.conn.execute(
        "SELECT count(*) c FROM document_fts_uni WHERE document_fts_uni MATCH 'beta'"
    ).fetchone()["c"] == 0
    assert len(r.search("beta")) == 1


def test_fts_deletes_with_document(repo):
    r, db, pid = repo
    did = _add(db, pid, title="t", body="ephemeral text", language="en")
    db.conn.execute("DELETE FROM document WHERE id=?", (did,))
    db.conn.commit()
    assert r.search("ephemeral") == []


# -- メタデータフィルタ・ソート --------------------------------------------------
def test_metadata_filters_and_sort(repo):
    r, db, pid = repo
    _add(db, pid, title="A", body="x", author="徳川慶喜", year=1867, language="ja", era="江戸後期")
    _add(db, pid, title="B", body="y", author="勝海舟", year=1860, language="ja", era="江戸後期")
    _add(db, pid, title="C", body="z", author="Perry", year=1853, language="en")

    assert {d.title for d in r.search(language="ja")} == {"A", "B"}
    assert {d.title for d in r.search(author="徳川")} == {"A"}
    assert {d.title for d in r.search(year_min=1860, year_max=1900)} == {"A", "B"}

    by_year = [d.title for d in r.search(order_by="year")]
    assert by_year == ["C", "B", "A"]
    by_year_desc = [d.title for d in r.search(order_by="year", descending=True)]
    assert by_year_desc == ["A", "B", "C"]


def test_coded_status_filter(repo):
    r, db, pid = repo
    coded = _add(db, pid, title="coded", body="x", language="ja")
    _add(db, pid, title="plain", body="y", language="ja")
    # coded ドキュメントにセグメントを 1 つ付与
    code = db.conn.execute(
        "INSERT INTO code(project_id, name) VALUES (?, 'c') RETURNING id", (pid,)
    ).fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'me') RETURNING id", (pid,)
    ).fetchone()["id"]
    db.conn.execute(
        "INSERT INTO segment(document_id, code_id, coder_id, char_start, char_end) "
        "VALUES (?, ?, ?, 0, 3)",
        (coded, code, coder),
    )
    db.conn.commit()

    assert [d.title for d in r.search(coded=True)] == ["coded"]
    assert [d.title for d in r.search(coded=False)] == ["plain"]
    assert next(d for d in r.search() if d.title == "coded").code_count == 1


# -- コレクション / タグ ---------------------------------------------------------
def test_collections_grouping(repo):
    r, db, pid = repo
    d1 = _add(db, pid, title="書簡1", body="x", language="ja")
    d2 = _add(db, pid, title="書簡2", body="y", language="ja")
    _add(db, pid, title="他", body="z", language="ja")

    col = r.create_collection(pid, "江戸後期書簡集")
    r.add_to_collection(d1, col)
    r.add_to_collection(d2, col)

    titles = {d.title for d in r.search(collection_id=col)}
    assert titles == {"書簡1", "書簡2"}
    assert r.collections(pid)[0]["doc_count"] == 2

    r.remove_from_collection(d2, col)
    assert {d.title for d in r.search(collection_id=col)} == {"書簡1"}


def test_year_range_and_languages(repo):
    r, db, pid = repo
    _add(db, pid, title="A", body="x", year=1867, language="ja")
    _add(db, pid, title="B", body="y", year=1853, language="en")
    assert r.year_range(pid) == (1853, 1867)
    assert r.distinct_languages(pid) == ["en", "ja"]


# -- Zotero 連携 -----------------------------------------------------------------
def test_zotero_better_bibtex_parsing():
    payload = """
    {"items": [
      {"citationKey": "tokugawa1867", "title": "大政奉還上表文",
       "creators": [{"lastName": "徳川", "firstName": "慶喜", "creatorType": "author"}],
       "date": "1867-11-09", "language": "ja", "publicationTitle": "幕末史料集"}
    ]}
    """
    entries = zotero.load_zotero_json(payload)
    assert len(entries) == 1
    e = entries[0]
    assert e.key == "tokugawa1867"
    assert e.year == 1867
    assert e.authors == ["徳川　慶喜"]
    meta = e.to_metadata()
    assert meta["language"] == "ja"
    assert meta["source"] == "幕末史料集"


def test_zotero_csl_json_and_apply(tmp_path):
    db = Database(tmp_path / "z.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, 'doc', '') RETURNING id",
        (pid,),
    ).fetchone()["id"]
    db.conn.commit()

    csl = '[{"id": "k1", "title": "T", "author": [{"family": "Perry", "given": "M."}], '
    csl += '"issued": {"date-parts": [[1853]]}, "language": "en"}]'
    entries = zotero.load_zotero_json(csl)
    assert entries[0].year == 1853
    zotero.apply_to_document(db, did, entries[0])
    row = db.conn.execute("SELECT author, year FROM document WHERE id=?", (did,)).fetchone()
    assert row["author"] == "Perry　M."
    assert row["year"] == 1853
    db.close()


# -- Obsidian 連携 ---------------------------------------------------------------
def test_extract_wikilinks():
    text = "本文 [[徳川慶喜]] と [[大政奉還|奉還]] と [[幕末#年表]] と再掲 [[徳川慶喜]]"
    assert obsidian.extract_wikilinks(text) == ["徳川慶喜", "大政奉還", "幕末"]


def test_scan_and_import_vault(tmp_path):
    from shiryo_coder.modules.ocr.markdown_writer import write_markdown

    vault = tmp_path / "vault"
    write_markdown(
        vault / "a.md",
        {"title": "書簡A", "author": "徳川慶喜", "year": 1867, "language": "ja"},
        "本文に [[書簡B]] への参照あり",
    )
    write_markdown(vault / "b.md", {"title": "書簡B", "language": "ja"}, "本文B")

    assert obsidian.is_vault(vault)
    notes = obsidian.scan_vault(vault)
    assert [n.title for n in notes] == ["書簡A", "書簡B"]
    assert notes[0].wikilinks == ["書簡B"]

    db = Database(tmp_path / "v.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    db.conn.commit()
    ids = obsidian.import_vault(db, pid, vault)
    assert len(ids) == 2
    # 取り込んだ日本語ドキュメントは FTS で検索できる
    assert len(LibraryRepository(db).search("本文B")) == 1
    db.close()
