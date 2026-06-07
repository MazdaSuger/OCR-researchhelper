"""外部評価極性辞書のダウンロード式インストーラ（仕様書 3.4）。

東北大 日本語評価極性辞書（用言編/名詞編）と高村 単語感情極性対応表（PN Table）は
第三者の著作物で、配布条件（研究利用・引用要件、再配布の可否が不明確）があるため、
本リポジトリには **同梱しない**。代わりに、ユーザーの環境で公式配布元から取得
（または手元のファイルを指定）し、本アプリの正規化形式（語\\t極性）へ変換して
ローカルのデータディレクトリにキャッシュする。

- 公式配布元からの取得は利用者がライセンスに同意して行う前提。
- 解析後のキャッシュ（`~/.shiryo_coder/dictionaries/<key>.tsv`）は派生物であり、
  再配布しないこと。引用要件は `DictionarySource.citation` を参照。
"""

from __future__ import annotations

import io
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from shiryo_coder.config import data_home
from shiryo_coder.modules.sentiment.dictionary import SentimentDictionary


def dictionaries_dir() -> Path:
    path = data_home() / "dictionaries"
    path.mkdir(parents=True, exist_ok=True)
    return path


# -- パーサ（実ファイル形式に対応） --------------------------------------------
def parse_takamura(text: str) -> dict[str, float]:
    """高村 PN Table（`語:よみ:品詞:極性値[-1..1]`、コロン区切り）。"""
    words: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 2:
            try:
                words[parts[0]] = float(parts[-1])
            except ValueError:
                continue
    return words


def parse_tohoku_wago(text: str) -> dict[str, float]:
    """東北大 用言編（`極性ラベル\\t分かち書き用言`）。ポジ→+1 / ネガ→-1 / 中立→0。"""
    words: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2:
            continue
        label, phrase = parts[0], parts[1]
        word = phrase.replace(" ", "").replace("　", "")
        if not word:
            continue
        if label.startswith("ポジ"):
            words[word] = 1.0
        elif label.startswith("ネガ"):
            words[word] = -1.0
        else:
            words.setdefault(word, 0.0)
    return words


def parse_tohoku_noun(text: str) -> dict[str, float]:
    """東北大 名詞編（`語\\t p/n/e \\t…`）。p→+1 / n→-1 / e→0。"""
    mapping = {"p": 1.0, "n": -1.0, "e": 0.0}
    words: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2 and parts[0]:
            value = mapping.get(parts[1].strip().lower())
            if value is not None:
                words[parts[0]] = value
    return words


_PARSERS = {
    "parse_takamura": parse_takamura,
    "parse_tohoku_wago": parse_tohoku_wago,
    "parse_tohoku_noun": parse_tohoku_noun,
}


@dataclass(frozen=True)
class DictionarySource:
    key: str
    name: str
    language: str
    url: str                  # 既定の公式配布元（環境により到達不可な場合あり）
    encoding: str
    parser: str
    license: str
    citation: str
    member_hint: str = ""     # 書庫内の対象ファイル名の手がかり


SOURCES: dict[str, DictionarySource] = {
    "takamura_pn": DictionarySource(
        key="takamura_pn",
        name="高村 単語感情極性対応表（PN Table）",
        language="ja",
        url="http://www.lr.pi.titech.ac.jp/~takamura/pubs/pn_ja.dic",
        encoding="euc-jp",
        parser="parse_takamura",
        license="研究目的に限り自由に利用可。再配布の可否は不明確（配布元の規定に従う）。",
        citation="高村大也, 乾孝司, 奥村学. 「スピンモデルによる単語の感情極性抽出」"
                 "情報処理学会論文誌, 47(2), 2006.",
        member_hint="pn_ja.dic",
    ),
    "tohoku_wago": DictionarySource(
        key="tohoku_wago",
        name="東北大 日本語評価極性辞書（用言編）",
        language="ja",
        url="http://www.cl.ecei.tohoku.ac.jp/resources/sent_lex/wago.121808.pn",
        encoding="utf-8",
        parser="parse_tohoku_wago",
        license="研究利用可。利用時は参考文献を引用すること（配布元の規定に従う）。",
        citation="小林のぞみ, 乾健太郎, 松本裕治, 立石健二, 福島俊一. "
                 "「意見抽出のための評価表現の収集」自然言語処理, 12(3), 2005.",
        member_hint="wago",
    ),
    "tohoku_noun": DictionarySource(
        key="tohoku_noun",
        name="東北大 日本語評価極性辞書（名詞編）",
        language="ja",
        url="http://www.cl.ecei.tohoku.ac.jp/resources/sent_lex/pn.csv.m3.120408.trim",
        encoding="utf-8",
        parser="parse_tohoku_noun",
        license="研究利用可。利用時は参考文献を引用すること（配布元の規定に従う）。",
        citation="東山昌彦, 乾健太郎, 松本裕治. "
                 "「述語の選択選好性に着目した名詞評価極性の獲得」言語処理学会年次大会, 2008.",
        member_hint="pn.csv",
    ),
}


def _decode(data: bytes, encoding: str) -> str:
    for enc in (encoding, "utf-8", "euc-jp", "cp932", "shift_jis"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode(encoding, errors="replace")


def _extract_member(data: bytes, hint: str) -> bytes:
    """tar.gz / zip ならヒントに合うメンバを取り出す。書庫でなければそのまま返す。"""
    if data[:2] == b"PK":  # zip
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = _pick(zf.namelist(), hint)
            return zf.read(name)
    if data[:2] == b"\x1f\x8b" or data[:3] == b"BZh":  # gzip / bzip2 tar
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            name = _pick(tf.getnames(), hint)
            return tf.extractfile(name).read()
    return data


def _pick(names: list[str], hint: str) -> str:
    candidates = [n for n in names if not n.endswith("/")]
    if hint:
        for n in candidates:
            if hint in n:
                return n
    return candidates[0]


def download(url: str, *, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Shiryo-Coder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 公式辞書取得
        return resp.read()


def install(
    key: str,
    *,
    path: str | Path | None = None,
    url: str | None = None,
    dest_dir: Path | None = None,
) -> Path:
    """辞書を取得・解析し、正規化キャッシュ（語\\t極性）を書き出してパスを返す。

    `path` 指定時は手元のファイル（公式配布元から取得済み）を使う。未指定なら
    `url`（既定はソースの公式 URL）からダウンロードする。
    """
    if key not in SOURCES:
        raise KeyError(f"未知の辞書: {key}（利用可能: {', '.join(SOURCES)}）")
    source = SOURCES[key]

    if path is not None:
        data = Path(path).read_bytes()
    else:
        data = download(url or source.url)

    raw = _extract_member(data, source.member_hint)
    text = _decode(raw, source.encoding)
    words = _PARSERS[source.parser](text)
    if not words:
        raise ValueError(f"辞書 '{key}' から語を抽出できませんでした（形式を確認）。")

    out = (dest_dir or dictionaries_dir()) / f"{key}.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(f"{w}\t{p}" for w, p in words.items()) + "\n", encoding="utf-8"
    )
    return out


def cache_path(key: str, *, dest_dir: Path | None = None) -> Path:
    return (dest_dir or dictionaries_dir()) / f"{key}.tsv"


def is_installed(key: str, *, dest_dir: Path | None = None) -> bool:
    return cache_path(key, dest_dir=dest_dir).exists()


def installed(*, dest_dir: Path | None = None) -> list[str]:
    return [k for k in SOURCES if is_installed(k, dest_dir=dest_dir)]


def load_external(key: str, *, dest_dir: Path | None = None) -> SentimentDictionary:
    """インストール済みの正規化キャッシュを SentimentDictionary として読み込む。"""
    if not is_installed(key, dest_dir=dest_dir):
        raise FileNotFoundError(f"辞書 '{key}' は未導入です。install() を実行してください。")
    source = SOURCES[key]
    words: dict[str, float] = {}
    for line in cache_path(key, dest_dir=dest_dir).read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            w, p = line.split("\t", 1)
            try:
                words[w] = float(p)
            except ValueError:
                continue
    negations = SentimentDictionary.builtin(source.language).negations
    return SentimentDictionary(source.language, words, set(negations), name=key)


def load_combined(language: str = "ja", *, dest_dir: Path | None = None) -> SentimentDictionary:
    """内蔵シードに、導入済みの外部辞書（同一言語）を重ねた辞書を返す。"""
    result = SentimentDictionary.builtin(language)
    for key in installed(dest_dir=dest_dir):
        if SOURCES[key].language == language:
            result = result.merge(load_external(key, dest_dir=dest_dir))
    return result
