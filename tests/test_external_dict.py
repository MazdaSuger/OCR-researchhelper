"""外部評価極性辞書インストーラ（3.4）のテスト。

ライセンス上、実辞書は同梱しない。実ファイル形式を模した合成フィクスチャで
パーサと install/load を検証する（ネットワークは使わない）。
"""

from __future__ import annotations

import gzip
import io
import tarfile

import pytest

from shiryo_coder.modules.sentiment import (
    SOURCES,
    SentimentAnalyzer,
    install,
    is_installed,
    load_combined,
    load_external,
)
from shiryo_coder.modules.sentiment.external import (
    parse_takamura,
    parse_tohoku_noun,
    parse_tohoku_wago,
)

# 実形式を模した小さなフィクスチャ
_TAKAMURA = "優れる:すぐれる:動詞:1\n良い:よい:形容詞:0.999995\nない:ない:助動詞:-0.999997\n"
_TOHOKU_WAGO = "ポジ（評価）\t優れ る\nネガ（評価）\t劣 る\n中立（経験）\t見 る\n"
_TOHOKU_NOUN = "名誉\tp\t〜（評価）\n恥\tn\t〜（評価）\n机\te\t〜\n"


# -- パーサ ----------------------------------------------------------------------
def test_parse_takamura_format():
    words = parse_takamura(_TAKAMURA)
    assert words["優れる"] == pytest.approx(1.0)
    assert words["ない"] == pytest.approx(-0.999997)


def test_parse_tohoku_wago_format():
    words = parse_tohoku_wago(_TOHOKU_WAGO)
    assert words["優れる"] == 1.0          # 分かち書きの空白は除去
    assert words["劣る"] == -1.0
    assert words["見る"] == 0.0


def test_parse_tohoku_noun_format():
    words = parse_tohoku_noun(_TOHOKU_NOUN)
    assert words["名誉"] == 1.0 and words["恥"] == -1.0 and words["机"] == 0.0


# -- install / load（ローカルファイル指定、ネットワークなし） -------------------
def test_install_from_path_and_load(tmp_path):
    src = tmp_path / "pn_ja.dic"
    src.write_text(_TAKAMURA, encoding="utf-8")
    dest = tmp_path / "dicts"

    out = install("takamura_pn", path=src, dest_dir=dest)
    assert out.exists()
    assert is_installed("takamura_pn", dest_dir=dest)

    d = load_external("takamura_pn", dest_dir=dest)
    assert d.name == "takamura_pn"
    assert d.polarity("優れる") == pytest.approx(1.0)
    # 否定語は内蔵から引き継ぐ
    assert d.is_negation("ず")


def test_install_euc_jp_encoding(tmp_path):
    # 高村辞書は EUC-JP 配布。バイト列から正しくデコードできること
    src = tmp_path / "pn.dic"
    src.write_bytes(_TAKAMURA.encode("euc-jp"))
    dest = tmp_path / "d"
    install("takamura_pn", path=src, dest_dir=dest)
    assert load_external("takamura_pn", dest_dir=dest).polarity("良い") > 0


def test_install_from_targz_archive(tmp_path):
    # 高村辞書は tar.gz 配布。書庫からメンバを取り出せること
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = _TAKAMURA.encode("euc-jp")
        info = tarfile.TarInfo("pndic_ja/pn_ja.dic")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    archive = tmp_path / "pndic_ja.tar.gz"
    archive.write_bytes(buf.getvalue())

    dest = tmp_path / "d"
    install("takamura_pn", path=archive, dest_dir=dest)
    assert load_external("takamura_pn", dest_dir=dest).polarity("優れる") == pytest.approx(1.0)


def test_load_combined_merges_external(tmp_path):
    dest = tmp_path / "d"
    (tmp_path / "noun").write_text(_TOHOKU_NOUN, encoding="utf-8")
    install("tohoku_noun", path=tmp_path / "noun", dest_dir=dest)

    combined = load_combined("ja", dest_dir=dest)
    # 内蔵語と外部語の両方が引ける
    assert combined.polarity("忠義") == pytest.approx(0.7)   # 内蔵
    assert combined.polarity("机") == 0.0                     # 外部（名詞編）


def test_external_dictionary_improves_coverage(tmp_path):
    dest = tmp_path / "d"
    (tmp_path / "wago").write_text(_TOHOKU_WAGO, encoding="utf-8")
    install("tohoku_wago", path=tmp_path / "wago", dest_dir=dest)
    d = load_combined("ja", dest_dir=dest)
    analyzer = SentimentAnalyzer(d, tokenizer="auto")
    # 内蔵に無い「優れる」が外部辞書で解析できる
    assert analyzer.score_text("実に優れた人物").polarity > 0


def test_sources_have_license_and_citation():
    for src in SOURCES.values():
        assert src.license and src.citation and src.url
