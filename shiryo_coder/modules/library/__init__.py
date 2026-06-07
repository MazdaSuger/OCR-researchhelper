"""3.2 .md ライブラリ管理モジュール。

責務:
- 三カラムレイアウト（フォルダ/コレクション・ドキュメント一覧・プレビュー）
- メタデータフィルタ（年代・著者・言語・コード付与状況）
- 言語別 FTS5 全文検索（日本語 trigram / 英語 unicode61）を横断検索
- タグ・コレクション（横断グルーピング）
- Zotero 連携（Better BibTeX / CSL-JSON）
- Obsidian 互換モード（[[wikilink]] 保持）

公開 API:
- `LibraryRepository`, `DocumentSummary`: 検索/集計/コレクション
- `zotero`, `obsidian`: 外部連携サブモジュール
"""

from shiryo_coder.modules.library.repository import DocumentSummary, LibraryRepository

__all__ = ["LibraryRepository", "DocumentSummary"]
