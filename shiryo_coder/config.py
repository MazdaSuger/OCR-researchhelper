"""アプリ設定とパス解決。

環境変数 `SHIRYO_HOME` でデータディレクトリを上書きできる（テスト用にも利用）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def data_home() -> Path:
    """アプリのデータディレクトリ（DB・設定の保存先）を返す。"""
    override = os.environ.get("SHIRYO_HOME")
    base = Path(override) if override else Path.home() / ".shiryo_coder"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass(frozen=True)
class AppConfig:
    """アプリ全体の実行時設定。"""

    db_path: Path

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(db_path=data_home() / "shiryo.db")
