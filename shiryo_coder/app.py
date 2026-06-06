"""QApplication エントリポイント。

DB を初期化し、メインウィンドウを表示する。
ヘッドレス環境（CI・テスト）では `--init-only` で GUI を起動せず DB 初期化のみ行える。
"""

from __future__ import annotations

import argparse
import sys

from shiryo_coder.config import AppConfig
from shiryo_coder.db import Database


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="shiryo-coder", description="史料コーダー")
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="GUI を起動せず DB の初期化のみ実行する（CI/検証用）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    config = AppConfig.default()

    db = Database(config.db_path)
    db.initialize()

    if args.init_only:
        print(f"DB を初期化しました: {config.db_path} (schema v{db.schema_version()})")
        db.close()
        return 0

    # GUI は遅延 import（ヘッドレス環境で PySide6 を要求しないため）
    from PySide6.QtWidgets import QApplication

    from shiryo_coder.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
