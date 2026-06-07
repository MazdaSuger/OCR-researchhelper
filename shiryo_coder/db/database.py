"""SQLite 接続・初期化・FTS5 セットアップ。"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

SCHEMA_VERSION = "3"

# 英語系言語（unicode61 索引へ振り分ける）。それ以外は trigram。
_LATIN_LANGS = ("en", "eng", "english")


def _load_schema() -> str:
    """パッケージ同梱の schema.sql を読み込む。"""
    return resources.files("shiryo_coder.db").joinpath("schema.sql").read_text(encoding="utf-8")


def connect(db_path: Path | str) -> sqlite3.Connection:
    """SQLite 接続を生成し、外部キーと行ファクトリを設定する。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def fts5_available(conn: sqlite3.Connection) -> bool:
    """この SQLite ビルドで FTS5（trigram）が使えるか判定する。"""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x, tokenize='trigram')"
        )
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


class Database:
    """アプリのデータベースハンドル。スキーマ適用と接続管理を担う。"""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.conn = connect(self.db_path)

    def initialize(self) -> None:
        """スキーマを適用し、バージョン情報を記録する（冪等・マイグレーション込み）。"""
        if not fts5_available(self.conn):
            raise RuntimeError(
                "この SQLite ビルドは FTS5 を含んでいません。"
                "全文検索のために FTS5 対応の SQLite が必要です。"
            )
        existing = self.schema_version()
        if existing == "1":
            self._drop_v1_fts()
        self.conn.executescript(_load_schema())
        if existing == "1":
            self.rebuild_fts()
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('version', ?)",
            (SCHEMA_VERSION,),
        )
        self.conn.commit()

    def _drop_v1_fts(self) -> None:
        """v1 の単一 trigram FTS とそのトリガを撤去する。"""
        for trigger in ("document_ai", "document_ad", "document_au"):
            self.conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        self.conn.execute("DROP TABLE IF EXISTS document_fts")

    def rebuild_fts(self) -> None:
        """既存 document から言語別 FTS 索引を作り直す。"""
        placeholders = ", ".join("?" for _ in _LATIN_LANGS)
        self.conn.execute("DELETE FROM document_fts_tri")
        self.conn.execute("DELETE FROM document_fts_uni")
        self.conn.execute(
            f"INSERT INTO document_fts_uni(rowid, title, body) "
            f"SELECT id, title, body FROM document WHERE language IN ({placeholders})",
            _LATIN_LANGS,
        )
        self.conn.execute(
            f"INSERT INTO document_fts_tri(rowid, title, body) "
            f"SELECT id, title, body FROM document "
            f"WHERE language IS NULL OR language NOT IN ({placeholders})",
            _LATIN_LANGS,
        )
        self.conn.commit()

    def schema_version(self) -> str | None:
        """記録済みスキーマバージョンを返す（未初期化なら None）。"""
        try:
            row = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return row["value"] if row else None

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
