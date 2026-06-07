-- Shiryō-Coder コアスキーマ
-- 仕様書「2. データモデル（コア概念）」に対応。
--
-- Project ─┬─ Document (.md + 元画像)
--          │    ├─ Segment (文字オフセット範囲 + コーダーID + コードID)
--          │    │    ├─ Memo (注釈)
--          │    │    └─ Sentiment (極性値)
--          │    └─ Metadata (YAML: 著者/年代/出典/言語)
--          ├─ CodeBook (コードツリー、定義、色)
--          ├─ Coder (研究者アカウント、色割当)
--          └─ Relations (コード間関係、共起ログ)

PRAGMA foreign_keys = ON;

-- スキーマバージョン（マイグレーション管理用）
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- プロジェクト ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- コーダー（研究者アカウント） ------------------------------------------------
-- role: admin / coder / viewer（仕様書 3.7 コーダーアカウント管理）
CREATE TABLE IF NOT EXISTS coder (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'coder'
                   CHECK (role IN ('admin', 'coder', 'viewer')),
    color      TEXT,                              -- コーダー別配色 (#RRGGBB)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ドキュメント（.md 本文 + 付随メタデータ） -----------------------------------
-- メタデータは YAML Front Matter 由来。検索・ソート対象の主要項目は
-- 正規化列として保持し、その他は metadata_json に格納する。
CREATE TABLE IF NOT EXISTS document (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',        -- OCR/翻刻済み本文（コーディング対象）
    file_path    TEXT,                            -- .md の実体パス
    author       TEXT,
    year         INTEGER,
    era          TEXT,
    language     TEXT,                            -- ja / en など
    script       TEXT,                            -- vertical / horizontal
    source_image TEXT,
    ocr_engine   TEXT,
    confidence   REAL,
    metadata_json TEXT,                           -- 上記以外の YAML 項目
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_document_project ON document(project_id);
CREATE INDEX IF NOT EXISTS idx_document_year    ON document(year);

-- コードブック（無制限階層ツリー） --------------------------------------------
-- parent_id が NULL なら最上位コード。
CREATE TABLE IF NOT EXISTS code (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    parent_id   INTEGER REFERENCES code(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    definition  TEXT,                             -- 説明文・包含/除外基準
    color       TEXT,                             -- #RRGGBB
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_code_project ON code(project_id);
CREATE INDEX IF NOT EXISTS idx_code_parent  ON code(parent_id);

-- セグメント（コーディング実体） ----------------------------------------------
-- 仕様書: 「文字オフセット start/end + コーダーID + コードID」。
-- 重複コード・部分重なり・複数コーダーの同一箇所コーディングを許容するため、
-- (document, char range, coder, code) の組み合わせごとに1行を持つ。
CREATE TABLE IF NOT EXISTS segment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    code_id     INTEGER NOT NULL REFERENCES code(id)     ON DELETE CASCADE,
    coder_id    INTEGER NOT NULL REFERENCES coder(id)    ON DELETE CASCADE,
    char_start  INTEGER NOT NULL,                 -- 文字オフセット（包含）
    char_end    INTEGER NOT NULL,                 -- 文字オフセット（排他）
    status      TEXT NOT NULL DEFAULT 'draft'     -- 承認ワークフロー（3.7）
                    CHECK (status IN ('draft', 'reviewed', 'confirmed')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (char_end > char_start)
);

CREATE INDEX IF NOT EXISTS idx_segment_document ON segment(document_id);
CREATE INDEX IF NOT EXISTS idx_segment_code     ON segment(code_id);
CREATE INDEX IF NOT EXISTS idx_segment_coder    ON segment(coder_id);
CREATE INDEX IF NOT EXISTS idx_segment_range    ON segment(document_id, char_start, char_end);

-- メモ・注釈（3階層: プロジェクト / ドキュメント / セグメント） ---------------
-- 対象に応じて project_id / document_id / segment_id のいずれかが埋まる。
CREATE TABLE IF NOT EXISTS memo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES project(id)  ON DELETE CASCADE,
    document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
    segment_id  INTEGER REFERENCES segment(id)  ON DELETE CASCADE,
    coder_id    INTEGER REFERENCES coder(id)    ON DELETE SET NULL,
    content     TEXT NOT NULL DEFAULT '',        -- Markdown
    is_journal  INTEGER NOT NULL DEFAULT 0,      -- ジャーナル機能フラグ
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memo_document ON memo(document_id);
CREATE INDEX IF NOT EXISTS idx_memo_segment  ON memo(segment_id);

-- センチメント（辞書ベース極性値） --------------------------------------------
-- 分析単位: 文 / 段落 / セグメント / 文書全体（仕様書 3.4）。
CREATE TABLE IF NOT EXISTS sentiment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    segment_id  INTEGER REFERENCES segment(id) ON DELETE CASCADE,
    unit        TEXT NOT NULL DEFAULT 'segment'
                    CHECK (unit IN ('sentence', 'paragraph', 'segment', 'document')),
    char_start  INTEGER,                          -- unit が文/段落のときの範囲
    char_end    INTEGER,
    polarity    REAL NOT NULL,                    -- -1.0 〜 +1.0
    dictionary  TEXT,                             -- 使用辞書名
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sentiment_document ON sentiment(document_id);

-- プロジェクト同梱のカスタム史料辞書（仕様書 3.4「我が君」「不忠」等に独自極性） --
CREATE TABLE IF NOT EXISTS sentiment_lexicon (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    word       TEXT NOT NULL,
    polarity   REAL NOT NULL,                     -- -1.0 〜 +1.0
    language   TEXT,                              -- ja / en など
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, word, language)
);

-- コード間関係（共起ログ・意味的関係） ----------------------------------------
-- relation_type 例: cooccurrence / 対立 / 包含 / 因果（仕様書 3.6）
CREATE TABLE IF NOT EXISTS code_relation (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    code_a_id     INTEGER NOT NULL REFERENCES code(id) ON DELETE CASCADE,
    code_b_id     INTEGER NOT NULL REFERENCES code(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL DEFAULT 'cooccurrence',
    weight        REAL NOT NULL DEFAULT 1.0,      -- 共起回数など
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_relation_project ON code_relation(project_id);

-- ドキュメントの排他ロック（共同作業 C. ロック方式: 仕様書 3.7） --------------
CREATE TABLE IF NOT EXISTS document_lock (
    document_id INTEGER PRIMARY KEY REFERENCES document(id) ON DELETE CASCADE,
    coder_id    INTEGER NOT NULL REFERENCES coder(id) ON DELETE CASCADE,
    acquired_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 変更履歴（誰がいつどのセグメントに何をしたか） -----------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    coder_id    INTEGER REFERENCES coder(id) ON DELETE SET NULL,
    entity      TEXT NOT NULL,                    -- 'segment' / 'code' / ...
    entity_id   INTEGER,
    action      TEXT NOT NULL,                    -- 'create' / 'update' / 'delete'
    detail_json TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- コレクション・タグ（横断グルーピング: 仕様書 3.2） -------------------------
CREATE TABLE IF NOT EXISTS collection (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'collection'
                   CHECK (kind IN ('collection', 'tag')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, kind, name)
);

CREATE TABLE IF NOT EXISTS document_collection (
    document_id   INTEGER NOT NULL REFERENCES document(id)   ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX IF NOT EXISTS idx_doccol_collection ON document_collection(collection_id);

-- 全文検索（FTS5、言語別トークナイザ） ----------------------------------------
-- 仕様書 3.2: 日本語(CJK)は trigram、英語(ラテン)は unicode61。
-- 言語に応じて document をどちらかの索引に振り分け（トリガ）、検索は両索引を横断する。
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts_tri USING fts5(
    title, body, tokenize='trigram'
);
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts_uni USING fts5(
    title, body, tokenize="unicode61 remove_diacritics 2"
);

-- 言語ルーティング: 英語系は unicode61、それ以外（日本語・不明）は trigram
CREATE TRIGGER IF NOT EXISTS document_ai_uni AFTER INSERT ON document
    WHEN new.language IN ('en', 'eng', 'english') BEGIN
        INSERT INTO document_fts_uni(rowid, title, body)
            VALUES (new.id, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS document_ai_tri AFTER INSERT ON document
    WHEN new.language IS NULL OR new.language NOT IN ('en', 'eng', 'english') BEGIN
        INSERT INTO document_fts_tri(rowid, title, body)
            VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS document_ad AFTER DELETE ON document BEGIN
    DELETE FROM document_fts_tri WHERE rowid = old.id;
    DELETE FROM document_fts_uni WHERE rowid = old.id;
END;

-- 更新: 複数トリガの発火順序は不定なので、各言語トリガ内で「両索引から削除→
-- 該当索引へ挿入」を完結させる（WHEN は相互排他なので片方のみ発火）。
CREATE TRIGGER IF NOT EXISTS document_au_uni AFTER UPDATE ON document
    WHEN new.language IN ('en', 'eng', 'english') BEGIN
        DELETE FROM document_fts_tri WHERE rowid = old.id;
        DELETE FROM document_fts_uni WHERE rowid = old.id;
        INSERT INTO document_fts_uni(rowid, title, body)
            VALUES (new.id, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS document_au_tri AFTER UPDATE ON document
    WHEN new.language IS NULL OR new.language NOT IN ('en', 'eng', 'english') BEGIN
        DELETE FROM document_fts_tri WHERE rowid = old.id;
        DELETE FROM document_fts_uni WHERE rowid = old.id;
        INSERT INTO document_fts_tri(rowid, title, body)
            VALUES (new.id, new.title, new.body);
END;
