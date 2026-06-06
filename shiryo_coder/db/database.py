"""SQLite 接続・初期化・FTS5 セットアップ。"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

SCHEMA_VERSION = "1"


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
        """スキーマを適用し、バージョン情報を記録する（冪等）。"""
        if not fts5_available(self.conn):
            raise RuntimeError(
                "この SQLite ビルドは FTS5 を含んでいません。"
                "全文検索のために FTS5 対応の SQLite が必要です。"
            )
        self.conn.executescript(_load_schema())
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('version', ?)",
            (SCHEMA_VERSION,),
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
