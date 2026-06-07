# Shiryō-Coder（史料コーダー）/ HistoryQDA

日英混在・縦横書き・大規模史料コーパスに対応した、研究室共有型の史料テキスト分析統合ソフトウェア。
QualCoder の操作感をベースに、OCR 取り込みから質的コーディング・センチメント分析・信頼性検証・共起可視化までを一気通貫で扱うことを目指します。

> 仕様書 3.1〜3.8 の全モジュール（OCR 取り込み・ライブラリ/検索・コーディング・
> センチメント分析・信頼性検証・共起可視化・共同作業・エクスポート）を実装済みです。
> 実装状況の一覧は [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) 末尾の表を参照してください。

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

## OCR 取り込み（仕様書 3.1）

入力（画像 jpg/png/tiff・**マルチページ TIFF**・PDF・ZIP・ディレクトリ）→ 前処理
（傾き補正/二値化/ノイズ除去）→ **言語・書字方向の自動判定（先頭ページの縮小推論）**
→ OCR → 手動校正 → `.md`（YAML Front Matter 付き）/ DB 保存、までを通しで扱います。

```bash
# 依存（ローカル OCR）をインストール
pip install -e ".[ocr]"
# Tesseract 本体と言語データも別途必要:
#   apt install tesseract-ocr tesseract-ocr-jpn tesseract-ocr-jpn-vert
# 日本語のフォント（自動判定の検証や描画に）: apt install fonts-noto-cjk
```

### GUI

```bash
python -m shiryo_coder        # メニュー「取り込み」→ファイル選択→設定確認→バッチOCR
```

「取り込み」ダイアログでは、先頭ページの自動判定結果（例「日本語縦書き」）を提示し、
エンジン・言語・方向・前処理をプレビューで確認/上書きできます。実行は QThreadPool の
バックグラウンドキューで進捗バー付き、低信頼度ページは「要校正」と表示されます。

### CLI（ヘッドレス）

```bash
# 言語/方向を指定しなければ先頭ページから自動判定（日本語縦書き等）
python -m shiryo_coder ingest path/to/scan.png --out doc.md
python -m shiryo_coder ingest path/to/scans.pdf --language ja --vertical

# 手動校正画面（左=元画像＋行ボックス／右=編集可能テキスト、相互ジャンプ）
python -m shiryo_coder correct path/to/scan.png
```

対応エンジン: `tesseract`（実装済み・ローカル）／ `ndlocr_lite`・`google_vision`・`vision_llm`
（インターフェース足場。SDK・認証情報・モデルの導入で有効化）。利用可否は
`shiryo_coder.modules.ocr.available_engines()` で確認できます。

> 並列 OCR 時の注意: Tesseract は既定で OpenMP により全コアを使うため、エンジン側で
> `OMP_THREAD_LIMIT=1` を設定し、QThreadPool での健全な並列化を確保しています。

## 外観（テーマ）

GUI は白・オレンジ・黒のモダンテーマで統一しています（`shiryo_coder/ui/theme.py`）。
グローバル QSS を QApplication に適用し全ウィジェットへカスケードするため、配色は
`PALETTE` の一箇所で変更できます（オレンジ＝主アクセント、白＝背景、黒＝文字）。

## ライブラリ管理 / 全文検索（仕様書 3.2）

取り込んだ史料は三カラムの史料カタログ（左＝コレクション/タグ、中央＝検索可能な
一覧、右＝プレビュー）で扱えます。

- **言語別 FTS5 全文検索**: 日本語（CJK）は `trigram`、英語（ラテン）は `unicode61` に
  自動ルーティングし、検索時は両索引を横断。2 文字以下の漢語は LIKE フォールバック。
- **メタデータフィルタ / ソート**: 年代・著者・言語・コード付与状況で絞り込み、各列で並び替え。
- **コレクション / タグ**: 「江戸後期書簡集」などで横断グルーピング。
- **Zotero 連携**: Better BibTeX / CSL-JSON を取り込み、著者・年・言語・出典を補完。
- **Obsidian 互換**: プロジェクトフォルダを Vault として走査し、`[[wikilink]]` を保持して取り込み。

検索 API は `shiryo_coder.modules.library.LibraryRepository`（`search()` ほか）です。

## コーディング（仕様書 3.3）

一覧で史料をダブルクリック（またはメニュー「コーディング」）すると、コードブック＋
本文ビューのコーディング画面が開きます。

- **階層コードブック**: 無制限階層、HSL 自動配色＋手動上書き、ドラッグ&ドロップで
  親子変更、REFI-QDA / QualCoder のコードブック XML 取り込み。
- **範囲選択コーディング**: 本文をマウス選択 → コード付与。**重複・部分重なりを許容**
  （1 文字に任意数のコード）。積層レイヤーで可視化。
- **可視化モード**: 下線色分け / ハイライト塗り。**他コーダーの付与は半透明**でレビュー。
- **キーボード駆動**: 数字キー 1–9 で頻用コードを選択範囲へ即時付与。
- **メモ 3 階層**（プロジェクト/ドキュメント/セグメント）とジャーナル。
- **AI 支援コーディング**: 既存コードの代表セグメントとの類似度で候補を提示（承認制、
  既定は文字 n-gram のオフライン埋め込み。`Embedder` 差し替えで高精度化可能）。

API: `shiryo_coder.modules.coding`（`CodebookRepository` / `CodingRepository` /
`MemoRepository` / `suggest_codes` ほか）。

## 信頼性検証（仕様書 3.5）

メニュー「分析 → 信頼性検証」で、複数コーダー間の一致率を算出できます。

- **一致係数**: Cohen's κ（2 コーダー）／ Fleiss' κ・Krippendorff's α（3 名以上、
  欠損データ・名義/間隔尺度に対応）。係数は手計算した既知値で検証済み。
- **算出単位**: 文字 / 文 / セグメント（一致判定の粒度を切替）。
- **不一致抽出**: 争点のある単位を一覧化し、協議用に CSV エクスポート。
- **コーダー研修モード**: マスターコーディングとの突き合わせで、見落とし（FN）・
  過剰付与（FP）・一致（TP）を逐次フィードバック。

API: `shiryo_coder.modules.reliability`（`ReliabilityRepository`、
`cohens_kappa` / `fleiss_kappa` / `krippendorff_alpha`）。

## 共起・関係性可視化（仕様書 3.6）

メニュー「分析 → 共起・関係性可視化」で、コード間の関係を可視化します。

- **共起マトリクス**: スコープ（重なり=同一セグメント / 同一段落 / 距離 N 文字以内）を
  切り替えてコード対の共起回数を集計。
- **ネットワーク図**: ノード径＝出現頻度、エッジ太さ＝共起回数。vis-network による
  自己完結 HTML を出力（外部 Python 依存なし。NetworkX があれば相互運用も可能）。
- **意味的関係の定義**: 「対立 / 包含 / 因果」などをエッジに付与。
- **ヒートマップ**: コード × 年代 / 著者 / 時代 / 言語のクロス集計、年代別の時系列。

API: `shiryo_coder.modules.cooccurrence`（`CooccurrenceRepository` /
`RelationRepository` / `HeatmapRepository` / `build_graph` / `to_html`）。

## センチメント分析（仕様書 3.4）

メニュー「分析 → センチメント分析」で、辞書ベースの極性分析を行います。

- **評価極性辞書**: 高村式（語＋連続値）・東北大式（posi/nega）・VADER 形式の読み込み、
  内蔵シード辞書（日英）、**プロジェクト同梱のカスタム史料辞書**（「我が君」「不忠」等に
  独自極性）。
- **史料語彙の正規化**: 旧字旧仮名 → 新字新仮名（内蔵マップ、ユーザー拡張可）。
- **形態素解析**: Sudachi（日本語）/ spaCy（英語）で活用語を辞書形（lemma）へ正規化して
  照合（「良くない」→ 良い＋否定、「嬉しかった」→ 嬉しい）。否定は日本語=後置・英語=前置で
  判定。未導入時は辞書の最長一致スキャンへ自動フォールバック。`pip install -e ".[nlp]"` で有効化。
- **解析**: 否定反転（oseti 互換）。任意の `tokenizer` を渡して MeCab 等へ差し替えも可能。
- **分析単位**: 文 / 段落 / コードセグメント / 文書全体。
- **集計**: 年代別の極性時系列、コード別の極性分布（平均・最小・最大）。

### 外部辞書の導入（東北大 / 高村）

東北大 日本語評価極性辞書（用言編/名詞編）と高村 単語感情極性対応表（PN Table）は
**第三者の著作物で再配布の可否が不明確なため、本リポジトリには同梱しません**。
利用者が配布元のライセンスに同意のうえ取得し、ダウンロード式インストーラで本アプリの
形式へ変換・キャッシュします（`~/.shiryo_coder/dictionaries/` に格納、派生物も再配布しないこと）。

```bash
# 既知の辞書とライセンス・導入状況を表示
python -m shiryo_coder dict list

# 手元に取得済みのファイルから導入（オフライン）
python -m shiryo_coder dict install takamura_pn --path ./pn_ja.dic
python -m shiryo_coder dict install tohoku_wago --path ./wago.121808.pn
python -m shiryo_coder dict install tohoku_noun --path ./pn.csv.m3.120408.trim

# 配布元 URL から取得（到達可能な環境のみ）
python -m shiryo_coder dict install takamura_pn
```

導入後は GUI の辞書選択に「内蔵＋外部（導入済み）」や各辞書が現れ、解析に利用できます。
利用時は各辞書の引用文献（`dict list` で表示）を明記してください。

API: `shiryo_coder.modules.sentiment`（`SentimentAnalyzer` / `SentimentDictionary` /
`SentimentRepository` / `LexiconRepository` / `OldToNewNormalizer` / `install` /
`load_external` / `load_combined`）。

## 共同作業（仕様書 3.7）

メニュー「共同作業」で、研究室共有のための運用機能を提供します。

- **アカウント管理＋役割権限**: 管理者 / コーダー / 閲覧者。閲覧者は読み取りのみ、
  承認・アカウント管理は管理者のみ、といった操作権限を役割で制御。
- **変更履歴**: 誰がいつどのセグメント・コードに何をしたかを `audit_log` に記録。
- **承認ワークフロー**: 「下書き(draft) → 主任承認(reviewed) → 確定(confirmed)」の
  三段階。承認・確定は管理者のみ実行可能。
- **ロック方式**: `document_lock` による同時編集の排他制御（取得/解放）。
- **差分共有（ファイル共有方式）**: コーディングを名前ベースの可搬レコードへ
  export し、別 DB へ import して統合。状態が食い違う箇所はコンフリクトとして報告。

API: `shiryo_coder.modules.collaboration`（`AccountRepository` / `AuditRepository` /
`ApprovalWorkflow` / `LockRepository` / `export_codings` / `import_codings`）。

## エクスポート・連携（仕様書 3.8）

メニュー「エクスポート」から各種出力を行います。

- **CSV / Excel**: コード集計表・セグメント一覧・メタデータ表・感情極性スコア
  （Excel は `pip install -e ".[export]"` の openpyxl で複数シート出力）。
- **REFI-QDA `.qdpx`**: MAXQDA / NVivo / ATLAS.ti / QualCoder 互換の交換形式
  （ZIP + project.qde、コード階層・色・コーディング・ユーザーを保持）。
- **学術引用形式**: セグメント引用文を APA / Chicago / SIST02（人文系日本）で生成。
- **Obsidian Vault**: コード=タグ、セグメント=callout、コード関係=`[[wikilink]]` で再構築。
- **HTML レポート**: コード階層・代表例・統計をまとめた自己完結 HTML。
- **SVG 可視化**: ヒートマップ（コード×メタデータ）・感情極性の時系列（外部依存なし）。
  共起ネットワークは vis-network HTML（3.6）で出力。

API: `shiryo_coder.modules.export`（`to_csv` / `to_excel` / `export_qdpx` /
`export_vault` / `build_report` / `format_citation` / `heatmap_svg` / `timeseries_svg`）。

## テスト

```bash
pytest
```

## ライセンス

PySide6 を LGPL v3 で利用します。プロジェクト本体のライセンスは別途決定予定です。
