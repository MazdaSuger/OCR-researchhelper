"""センチメント分析（3.4）のテスト（Qt 非依存）。"""

from __future__ import annotations

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.modules.sentiment import (
    LexiconRepository,
    OldToNewNormalizer,
    SentimentAnalyzer,
    SentimentDictionary,
    SentimentRepository,
    sudachi_available,
)

_needs_sudachi = pytest.mark.skipif(not sudachi_available(), reason="Sudachi が必要")


# -- 正規化 ---------------------------------------------------------------------
def test_old_to_new_normalization():
    norm = OldToNewNormalizer()
    assert norm.normalize("國學") == "国学"
    assert norm.normalize("ゐる") == "いる"
    norm.extend({"龍": "竜"})
    assert norm.normalize("龍") == "竜"


# -- 辞書 -----------------------------------------------------------------------
def test_dictionary_builtin_and_loaders():
    ja = SentimentDictionary.builtin("ja")
    assert ja.polarity("忠義") == pytest.approx(0.7)
    assert ja.is_negation("ず")

    taka = SentimentDictionary.from_takamura("良い\t0.9\n醜い\t-0.8")
    assert taka.polarity("良い") == pytest.approx(0.9)

    tohoku = SentimentDictionary.from_tohoku("名誉\tposi\n恥\tnega")
    assert tohoku.polarity("名誉") == 1.0
    assert tohoku.polarity("恥") == -1.0


def test_dictionary_merge_overrides():
    base = SentimentDictionary.builtin("ja")
    custom = SentimentDictionary("ja", {"忠": -0.9}, set())   # 史料文脈で再定義
    merged = base.merge(custom)
    assert merged.polarity("忠") == pytest.approx(-0.9)


# -- 解析 -----------------------------------------------------------------------
def test_analyze_japanese_polarity():
    analyzer = SentimentAnalyzer(SentimentDictionary.builtin("ja"))
    pos = analyzer.score_text("勝利の喜びと名誉")
    assert pos.polarity > 0 and pos.positive >= 2
    neg = analyzer.score_text("逆賊の罪と恥")
    assert neg.polarity < 0


def test_analyze_negation_flips_polarity():
    analyzer = SentimentAnalyzer(SentimentDictionary.builtin("ja"))
    # 辞書形で一致する名詞＋否定（活用語は形態素解析器を tokenizer に渡す前提）
    plain = analyzer.score_text("名誉")
    negated = analyzer.score_text("名誉がない")
    assert plain.polarity > 0
    assert negated.hits and negated.hits[0].negated
    assert negated.polarity < 0


def test_analyze_old_orthography():
    # 旧字「國」を含むカスタム辞書語が正規化後に一致する
    d = SentimentDictionary("ja", {"国": 0.5}, set())
    analyzer = SentimentAnalyzer(d)
    assert analyzer.score_text("我が國は").polarity == pytest.approx(0.5)


def test_analyze_english():
    analyzer = SentimentAnalyzer(SentimentDictionary.builtin("en"))
    assert analyzer.score_text("a great victory and honor").polarity > 0
    neg = analyzer.score_text("this is not good")
    assert neg.hits[-1].negated and neg.polarity < 0


# -- 形態素解析（Sudachi） ------------------------------------------------------
@_needs_sudachi
def test_morphology_handles_conjugation_and_negation():
    d = SentimentDictionary.builtin("ja")
    morph = SentimentAnalyzer(d, tokenizer="auto")
    plain = SentimentAnalyzer(d)

    # 活用語: 辞書スキャンは取りこぼすが、形態素解析は辞書形で一致
    assert plain.score_text("嬉しかった").word_count == 0
    assert morph.score_text("嬉しかった").polarity > 0

    # 活用＋否定: 「良くない」→ 良い(+)が否定で反転
    neg = morph.score_text("良くない")
    assert neg.hits and neg.hits[0].negated and neg.polarity < 0

    # 否定で肯定語が反転: 「勝利できなかった」
    assert morph.score_text("勝利できなかった").polarity < 0


@_needs_sudachi
def test_morphology_auto_tokenizer_selected():
    a = SentimentAnalyzer(SentimentDictionary.builtin("ja"), tokenizer="auto")
    assert a.tokenizer is not None
    # 英語で Sudachi のみ環境なら auto は None（フォールバック）
    b = SentimentAnalyzer(SentimentDictionary.builtin("en"), tokenizer="auto")
    assert b.score_text("a great victory").polarity > 0


# -- リポジトリ統合 -------------------------------------------------------------
@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "s.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coder = db.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, 'A') RETURNING id", (pid,)
    ).fetchone()["id"]
    yield db, pid, coder
    db.close()


def _doc(db, pid, body, *, year=None):
    row = db.conn.execute(
        "INSERT INTO document(project_id, title, body, year) VALUES (?, 'd', ?, ?) RETURNING id",
        (pid, body, year),
    ).fetchone()
    db.conn.commit()
    return row["id"]


def test_custom_lexicon_and_merge(env):
    db, pid, coder = env
    lex = LexiconRepository(db)
    lex.set_word(pid, "我が君", 0.8, language="ja")
    lex.set_word(pid, "不忠", -0.95, language="ja")     # 既定 -0.8 を上書き
    merged = lex.merged_with_builtin(pid, "ja")
    assert merged.polarity("我が君") == pytest.approx(0.8)
    assert merged.polarity("不忠") == pytest.approx(-0.95)


def test_analyze_document_by_sentence_persists(env):
    db, pid, coder = env
    did = _doc(db, pid, "勝利の喜び。逆賊の罪。")
    repo = SentimentRepository(db)
    analyzer = SentimentAnalyzer(SentimentDictionary.builtin("ja"))
    results = repo.analyze_document(did, analyzer, unit="sentence")
    assert len(results) == 2
    assert results[0].polarity > 0 and results[1].polarity < 0
    # 保存されている
    n = db.conn.execute(
        "SELECT COUNT(*) c FROM sentiment WHERE document_id=? AND unit='sentence'", (did,)
    ).fetchone()["c"]
    assert n == 2


def test_timeseries_and_by_code(env):
    db, pid, coder = env
    d1 = _doc(db, pid, "勝利の喜びと名誉。", year=1867)
    d2 = _doc(db, pid, "逆賊の罪と恥。", year=1860)
    repo = SentimentRepository(db)
    analyzer = SentimentAnalyzer(SentimentDictionary.builtin("ja"))
    repo.analyze_document(d1, analyzer, unit="document")
    repo.analyze_document(d2, analyzer, unit="document")

    series = repo.timeseries(pid, unit="document")
    assert series[1867] > 0 and series[1860] < 0

    # コード別: セグメント単位で解析 → コードに極性が紐づく
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "感情")
    body = "勝利の喜び"
    d3 = _doc(db, pid, body)
    cd.add_coding(d3, code, coder, 0, len(body))
    repo.analyze_document(d3, analyzer, unit="segment")
    by_code = repo.by_code(pid)
    assert code in by_code and by_code[code][0] > 0
