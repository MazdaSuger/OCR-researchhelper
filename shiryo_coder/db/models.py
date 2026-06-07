"""コアエンティティの dataclass 表現。

スキーマ（schema.sql）と1対1で対応する軽量データ保持用。
ORM は導入せず、必要に応じて行（sqlite3.Row）からの変換ヘルパとして用いる。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Project:
    id: int | None
    name: str
    description: str | None = None


@dataclass
class Coder:
    id: int | None
    project_id: int
    name: str
    role: str = "coder"          # admin / coder / viewer
    color: str | None = None


@dataclass
class Document:
    id: int | None
    project_id: int
    title: str
    body: str = ""
    file_path: str | None = None
    author: str | None = None
    year: int | None = None
    era: str | None = None
    language: str | None = None
    script: str | None = None     # vertical / horizontal
    source_image: str | None = None
    ocr_engine: str | None = None
    confidence: float | None = None


@dataclass
class Code:
    id: int | None
    project_id: int
    name: str
    parent_id: int | None = None
    definition: str | None = None
    color: str | None = None
    sort_order: int = 0


@dataclass
class Segment:
    """コーディング実体: 文字オフセット + コーダー + コード。"""

    id: int | None
    document_id: int
    code_id: int
    coder_id: int
    char_start: int
    char_end: int
    status: str = "draft"         # draft / reviewed / confirmed


@dataclass
class Memo:
    id: int | None
    content: str = ""
    project_id: int | None = None
    document_id: int | None = None
    segment_id: int | None = None
    coder_id: int | None = None
    is_journal: bool = False


@dataclass
class Sentiment:
    id: int | None
    document_id: int
    polarity: float
    unit: str = "segment"         # sentence / paragraph / segment / document
    segment_id: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    dictionary: str | None = None


@dataclass
class Collection:
    """横断グルーピング（コレクション / タグ）。"""

    id: int | None
    project_id: int
    name: str
    kind: str = "collection"      # collection / tag


@dataclass
class CodeRelation:
    id: int | None
    project_id: int
    code_a_id: int
    code_b_id: int
    relation_type: str = "cooccurrence"
    weight: float = 1.0
