# Shiryō-Coder（史料コーダー）/ HistoryQDA

日英混在・縦横書き・大規模史料コーパスに対応した、研究室共有型の史料テキスト分析統合ソフトウェア。
QualCoder の操作感をベースに、OCR 取り込みから質的コーディング・センチメント分析・信頼性検証・共起可視化までを一気通貫で扱うことを目指します。

> ⚠️ 本リポジトリは現在 **プロジェクト雛形（スキャフォールド）** の段階です。
> データモデル・モジュール境界・起動可能な最小 GUI シェルを定義しています。各モジュールの本実装はこれからです。

詳細な機能仕様は [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) を参照してください。

## アーキテクチャ概要

| 層 | 採用技術 |
| --- | --- |
| GUI | PySide6（Qt 6 / LGPL v3） |
| 言語 | Python 3.11+ |
| ローカル DB | SQLite + FTS5（全文検索, trigram） |
| 共有層 | PostgreSQL 同期 / Git LFS（将来対応） |
| ファイル実体 | `.md`（YAML Front Matter）＋画像 |
| プロジェクト形式 | `.shiryo`（zip）/ REFI-QDA `.qdpx` 互換エクスポート |

## ディレクトリ構成

```
shiryo_coder/
├── app.py              # QApplication エントリポイント
├── config.py           # アプリ設定・パス解決
├── db/
│   ├── database.py     # 接続・初期化・FTS5
│   ├── models.py       # コアエンティティ（dataclass）
│   └── schema.sql      # SQLite スキーマ
├── modules/            # 機能モジュール（仕様書 3.x に対応）
│   ├── ocr/            # 3.1 OCR 取り込み
│   ├── library/        # 3.2 .md ライブラリ管理
│   ├── coding/         # 3.3 コーディング（中核）
│   ├── sentiment/      # 3.4 センチメント分析
│   ├── reliability/    # 3.5 信頼性検証
│   ├── cooccurrence/   # 3.6 共起・関係性可視化
│   ├── collaboration/  # 3.7 共同作業
│   └── export/         # 3.8 エクスポート・連携
└── ui/
    └── main_window.py  # 三カラムのメインウィンドウシェル
```

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # もしくは pip install -r requirements.txt
```

## 起動

```bash
python -m shiryo_coder
```

初回起動時に `~/.shiryo_coder/shiryo.db` が作成され、スキーマが適用されます。

## OCR 取り込み（GUI なし）

OCR 取り込みモジュール（仕様書 3.1）はヘッドレスでも実行できます。

```bash
# 依存（ローカル OCR）をインストール
pip install -e ".[ocr]"
# Tesseract 本体と言語データも別途必要（例: apt install tesseract-ocr tesseract-ocr-jpn）

# 画像 / PDF / ZIP / ディレクトリを取り込み、.md（YAML Front Matter 付き）を出力
python -m shiryo_coder ingest path/to/scan.png --language ja --out doc.md
python -m shiryo_coder ingest path/to/scans.pdf --vertical   # 縦書き（PSM 5）
```

対応エンジン: `tesseract`（実装済み・ローカル）／ `ndlocr_lite`・`google_vision`・`vision_llm`
（インターフェース足場。SDK・認証情報・モデルの導入で有効化）。利用可否は
`shiryo_coder.modules.ocr.available_engines()` で確認できます。

## テスト

```bash
pytest
```

## ライセンス

PySide6 を LGPL v3 で利用します。プロジェクト本体のライセンスは別途決定予定です。
