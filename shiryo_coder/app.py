"""QApplication エントリポイント。

DB を初期化し、メインウィンドウを表示する。
ヘッドレス環境（CI・検証）では以下のサブコマンドを GUI なしで実行できる:
- `--init-only`     : DB の初期化のみ
- `ingest <path>`   : OCR 取り込みを実行し `.md` 保存 / DB 永続化（仕様書 3.1）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shiryo_coder.config import AppConfig
from shiryo_coder.db import Database


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shiryo-coder", description="史料コーダー")
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="GUI を起動せず DB の初期化のみ実行する（CI/検証用）",
    )

    sub = parser.add_subparsers(dest="command")
    ingest = sub.add_parser("ingest", help="OCR 取り込みを GUI なしで実行する")
    ingest.add_argument("path", help="画像 / PDF / ZIP / ディレクトリ")
    ingest.add_argument("--engine", default="tesseract", help="OCR エンジン名")
    ingest.add_argument("--language", help="言語コード（ja/en など。未指定で自動判定）")
    ingest.add_argument("--vertical", action="store_true", help="縦書きとして処理する")
    ingest.add_argument("--title", help="ドキュメントタイトル（既定は入力ファイル名）")
    ingest.add_argument("--out", help="保存先 .md パス")
    ingest.add_argument(
        "--no-preprocess", action="store_true", help="前処理（傾き補正等）を行わない"
    )

    correct = sub.add_parser("correct", help="手動校正画面を開く（GUI）")
    correct.add_argument("path", help="画像 / PDF / ZIP / ディレクトリ")
    correct.add_argument("--engine", default="tesseract", help="OCR エンジン名")
    correct.add_argument("--language", help="言語コード（ja/en など）")
    correct.add_argument("--vertical", action="store_true", help="縦書きとして処理する")
    correct.add_argument("--page", type=int, default=0, help="対象ページ（0 始まり）")
    return parser


def _run_ingest(args: argparse.Namespace, db: Database) -> int:
    from shiryo_coder.modules.ocr import OcrPipeline, get_engine
    from shiryo_coder.modules.ocr.preprocess import PreprocessConfig

    engine = get_engine(args.engine)
    if not engine.is_available():
        print(f"エンジン '{args.engine}' は利用できません（依存が不足しています）。", file=sys.stderr)
        return 2

    config = PreprocessConfig.none() if args.no_preprocess else PreprocessConfig()
    pipeline = OcrPipeline(engine=engine, preprocess_config=config)

    def progress(current: int, total: int) -> None:
        print(f"  OCR {current}/{total} ページ", file=sys.stderr)

    doc = pipeline.ingest(
        args.path,
        title=args.title,
        language=args.language,
        vertical=args.vertical or None,
        progress=progress,
    )

    out = Path(args.out) if args.out else Path(args.path).with_suffix(".md")
    pipeline.save_markdown(doc, out)
    conf = f"{doc.confidence:.3f}" if doc.confidence is not None else "N/A"
    print(
        f"取り込み完了: {out}  "
        f"(engine={doc.metadata['ocr_engine']}, language={doc.metadata['language']}, "
        f"confidence={conf}, {len(doc.body)} 文字)"
    )
    return 0


def _run_correct(args: argparse.Namespace) -> int:
    from PySide6.QtWidgets import QApplication, QMainWindow

    from shiryo_coder.modules.ocr import get_engine
    from shiryo_coder.modules.ocr.inputs import enumerate_pages
    from shiryo_coder.modules.ocr.preprocess import PreprocessConfig, preprocess
    from shiryo_coder.ui.correction import CorrectionWidget

    engine = get_engine(args.engine)
    if not engine.is_available():
        print(f"エンジン '{args.engine}' は利用できません。", file=sys.stderr)
        return 2

    pages = enumerate_pages(args.path)
    if not (0 <= args.page < len(pages)):
        print(f"ページ番号が範囲外です（0–{len(pages) - 1}）。", file=sys.stderr)
        return 2

    # OCR が走った画像をそのまま表示し、ボックス座標を一致させる
    image = preprocess(pages[args.page].load(), PreprocessConfig())
    result = engine.recognize(image, vertical=args.vertical, language=args.language)

    app = QApplication(sys.argv[:1])
    window = QMainWindow()
    window.setWindowTitle(f"校正: {Path(args.path).name} (p{args.page + 1})")
    window.setCentralWidget(
        CorrectionWidget(image, result, metadata={"source_image": str(args.path)})
    )
    window.resize(1100, 700)
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    config = AppConfig.default()

    if args.command == "correct":
        return _run_correct(args)

    db = Database(config.db_path)
    db.initialize()
    try:
        if args.command == "ingest":
            return _run_ingest(args, db)

        if args.init_only:
            print(f"DB を初期化しました: {config.db_path} (schema v{db.schema_version()})")
            return 0

        # GUI は遅延 import（ヘッドレス環境で PySide6 を要求しないため）
        from PySide6.QtWidgets import QApplication

        from shiryo_coder.ui.main_window import MainWindow

        app = QApplication(sys.argv[:1])
        window = MainWindow(db)
        window.show()
        return app.exec()
    finally:
        if args.command == "ingest" or args.init_only:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
