"""DB スキーマと FTS5 全文検索の最小テスト。"""

from __future__ import annotations

import sqlite3

import pytest

from shiryo_coder.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    yield database
    database.close()


def test_initialize_sets_schema_version(db: Database) -> None:
    assert db.schema_version() == "2"


def test_core_tables_exist(db: Database) -> None:
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    for table in (
        "project", "coder", "document", "code",
        "segment", "memo", "sentiment", "code_relation", "audit_log",
    ):
        assert table in names


def test_segment_requires_valid_range(db: Database) -> None:
    pid = db.conn.execute(
        "INSERT INTO project(name) VALUES ('p') RETURNING id"
    ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title) VALUES (?, 't') RETURNING id", (pid,)
    ).fetchone()["id"]
    cid = db.conn.execute(
        "INSERT INTO code(project_id, name) VALUES (?, 'c') RETURNING id", (pid,)
    ).fetchone()["id"]
    coder_id = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'me') RETURNING id", (pid,)
    ).fetchone()["id"]

    # char_end <= char_start は CHECK 制約で拒否される
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO segment(document_id, code_id, coder_id, char_start, char_end)"
            " VALUES (?, ?, ?, 10, 10)",
            (did, cid, coder_id),
        )


def test_fts_search_finds_document(db: Database) -> None:
    pid = db.conn.execute(
        "INSERT INTO project(name) VALUES ('p') RETURNING id"
    ).fetchone()["id"]
    db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, '大政奉還上表文', ?)",
        (pid, "朕惟フニ我皇祖皇宗國ヲ肇ムルコト宏遠ニ"),
    )
    db.conn.commit()

    # 言語未指定（NULL）の日本語ドキュメントは trigram 索引へルーティングされる
    hits = db.conn.execute(
        "SELECT rowid FROM document_fts_tri WHERE document_fts_tri MATCH ?", ("皇祖皇宗",)
    ).fetchall()
    assert len(hits) == 1
