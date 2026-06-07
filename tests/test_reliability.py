"""信頼性検証（3.5）のテスト。

一致係数は手計算した既知値で検証する。
"""

from __future__ import annotations

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.modules.reliability import (
    ReliabilityRepository,
    cohens_kappa,
    disagreements_to_csv,
    fleiss_kappa,
    krippendorff_alpha,
)
from shiryo_coder.modules.reliability import units as unit_mod


# -- 係数（手計算の既知値） -----------------------------------------------------
def test_cohens_kappa_known_value():
    assert cohens_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)


def test_cohens_kappa_perfect_and_chance():
    assert cohens_kappa([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    # 双方が同一の単一カテゴリ → 完全一致（pe=1 の特別扱い）
    assert cohens_kappa([1, 1, 1, 1], [1, 1, 1, 1]) == pytest.approx(1.0)
    # 各レーターが別々の単一カテゴリ → 期待一致 0、κ=0
    assert cohens_kappa([1, 1, 1, 1], [0, 0, 0, 0]) == pytest.approx(0.0)


def test_fleiss_kappa_known_value():
    # item1=[0,1], item2=[1,1] → κ = -1/3（手計算）
    assert fleiss_kappa([[0, 1], [1, 1]]) == pytest.approx(-1 / 3)


def test_krippendorff_alpha_known_value():
    # A=[0,0,1,1], B=[0,1,1,1] → α=0.5333（手計算）
    assert krippendorff_alpha([[0, 0, 1, 1], [0, 1, 1, 1]]) == pytest.approx(0.5333, abs=1e-4)


def test_krippendorff_handles_missing_data():
    # 多コーダー・欠損ありの例（手計算で α=0.675）
    A = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
    B = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
    C = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
    assert krippendorff_alpha([A, B, C]) == pytest.approx(0.675, abs=1e-3)


def test_krippendorff_interval_level():
    # 間隔尺度では値の差の二乗で重み付け
    assert krippendorff_alpha([[1, 2, 3], [1, 2, 3]], level="interval") == pytest.approx(1.0)


# -- 算出単位 -------------------------------------------------------------------
def test_sentence_spans():
    text = "朝廷は命じた。徳川は応じた。\n次の行"
    spans = unit_mod.sentence_spans(text)
    assert len(spans) == 3
    assert text[spans[0][0]:spans[0][1]] == "朝廷は命じた。"


# -- リポジトリ統合 -------------------------------------------------------------
@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "r.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    coders = {}
    for name in ("A", "B", "C"):
        coders[name] = db.conn.execute(
            "INSERT INTO coder(project_id, name) VALUES (?, ?) RETURNING id", (pid, name)
        ).fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, 'd', ?) RETURNING id",
        (pid, "0123456789"),                       # 10 文字、オフセットが明快
    ).fetchone()["id"]
    db.conn.commit()
    cb = CodebookRepository(db)
    code = cb.create_code(pid, "X")
    yield db, pid, coders, did, code, CodingRepository(db), ReliabilityRepository(db)
    db.close()


def test_two_coder_character_kappa(env):
    db, pid, coders, did, code, cd, rel = env
    # A: 0-5 をコード、B: 0-4 をコード（文字単位で 9/10 一致になるよう）
    cd.add_coding(did, code, coders["A"], 0, 5)
    cd.add_coding(did, code, coders["B"], 0, 4)
    result = rel.compute(did, code, [coders["A"], coders["B"]], "character")
    assert result.method == "cohen"
    assert result.n_units == 10
    # 文字 0-3=both1, 4=A1/B0, 5-9=both0 → po=9/10
    assert 0.0 < result.value < 1.0


def test_three_coders_fleiss_and_alpha(env):
    db, pid, coders, did, code, cd, rel = env
    for c in coders.values():
        cd.add_coding(did, code, c, 0, 5)          # 全員 0-5 を同一コード → 完全一致
    result = rel.compute(did, code, list(coders.values()), "character")
    assert result.method == "fleiss"
    assert result.value == pytest.approx(1.0)
    assert result.extra["krippendorff_alpha"] == pytest.approx(1.0)


def test_disagreements_extraction_and_csv(env):
    db, pid, coders, did, code, cd, rel = env
    cd.add_coding(did, code, coders["A"], 0, 6)
    cd.add_coding(did, code, coders["B"], 0, 3)    # 3-6 が不一致
    dis = rel.disagreements(did, code, [coders["A"], coders["B"]], "segment")
    assert dis                                     # 不一致区間あり
    assert any(d.labels[coders["A"]] != d.labels[coders["B"]] for d in dis)

    csv_text = disagreements_to_csv(dis, {coders["A"]: "A", coders["B"]: "B"})
    assert "start,end,text,A,B" in csv_text.splitlines()[0]


def test_training_feedback(env):
    db, pid, coders, did, code, cd, rel = env
    # マスター A: 0-6、研修者 B: 2-8（見落とし 0-2、過剰 6-8）
    cd.add_coding(did, code, coders["A"], 0, 6)
    cd.add_coding(did, code, coders["B"], 2, 8)
    fb = rel.training_feedback(did, code, coders["A"], coders["B"], "character")
    assert fb.false_negative == 2                  # 0,1 をマスターのみ
    assert fb.false_positive == 2                  # 6,7 を研修者のみ
    assert fb.true_positive == 4                   # 2..5 一致
    assert fb.missed and fb.extra
