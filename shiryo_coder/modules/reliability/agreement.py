"""コーダー間一致係数（仕様書 3.5）。

- Cohen's κ: 2 コーダー
- Fleiss' κ: 3 名以上（カテゴリ計数）
- Krippendorff's α: 任意人数・欠損可（名義/間隔尺度）

いずれも汎用のラベル列／計数を入力とする純関数。上位層（reliability.py）が
コーディング結果を単位ラベルに変換してここへ渡す。
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

Label = object


def cohens_kappa(a: Sequence[Label], b: Sequence[Label]) -> float:
    """2 コーダーのラベル列から Cohen's κ を計算する。

    どちらかが None の単位は除外する。完全一致のみ（一致は po）で、
    期待一致 pe は各コーダーの周辺分布の積和。
    """
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in pairs if x == y) / n
    count_a = Counter(x for x, _ in pairs)
    count_b = Counter(y for _, y in pairs)
    categories = set(count_a) | set(count_b)
    pe = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)
    if pe >= 1.0:
        return 1.0       # 双方が単一カテゴリのみ → 完全一致とみなす
    return (po - pe) / (1 - pe)


def fleiss_kappa(items: Sequence[Sequence[Label]]) -> float:
    """Fleiss' κ。`items[i]` は項目 i に対する各レーターのラベル列。

    項目ごとのレーター数は一定であることを前提とする（Fleiss の仮定）。
    """
    items = [list(it) for it in items if it]
    if not items:
        return float("nan")
    n_raters = len(items[0])
    if any(len(it) != n_raters for it in items):
        raise ValueError("Fleiss' κ は全項目で同数のレーターを要します。")
    if n_raters < 2:
        raise ValueError("レーターは 2 名以上必要です。")

    categories = sorted({label for it in items for label in it}, key=repr)
    cat_index = {c: j for j, c in enumerate(categories)}
    n_items = len(items)

    # 計数行列 n_ij
    counts = [[0] * len(categories) for _ in range(n_items)]
    for i, it in enumerate(items):
        for label in it:
            counts[i][cat_index[label]] += 1

    # 項目ごとの一致度 P_i
    p_i = [
        (sum(c * c for c in row) - n_raters) / (n_raters * (n_raters - 1))
        for row in counts
    ]
    p_bar = sum(p_i) / n_items

    # カテゴリ比率 p_j と期待一致 Pe
    total = n_items * n_raters
    p_j = [sum(counts[i][j] for i in range(n_items)) / total for j in range(len(categories))]
    pe = sum(p * p for p in p_j)

    if pe >= 1.0:
        return 1.0
    return (p_bar - pe) / (1 - pe)


def _nominal_delta(v: Label, w: Label) -> float:
    return 0.0 if v == w else 1.0


def _interval_delta(v: Label, w: Label) -> float:
    return float(v - w) ** 2


def krippendorff_alpha(
    data: Sequence[Sequence[Label | None]],
    *,
    level: str = "nominal",
) -> float:
    """Krippendorff's α。`data[c]` はコーダー c の単位ラベル列（欠損は None）。

    全コーダーの列長は等しいこと。各単位で 2 つ以上の評価がある単位のみ用いる。
    `level`: 'nominal' または 'interval'。
    """
    delta = _interval_delta if level == "interval" else _nominal_delta
    n_units = max((len(c) for c in data), default=0)

    # 各単位の評価値（欠損を除く）
    units: list[list[Label]] = []
    for u in range(n_units):
        values = [coder[u] for coder in data if u < len(coder) and coder[u] is not None]
        if len(values) >= 2:
            units.append(values)
    if not units:
        return float("nan")

    # 一致行列（coincidence matrix）を値ごとに集計
    coincidence: Counter[tuple[Label, Label]] = Counter()
    for values in units:
        m = len(values)
        weight = 1.0 / (m - 1)
        for i in range(m):
            for j in range(m):
                if i != j:
                    coincidence[(values[i], values[j])] += weight

    value_totals: Counter[Label] = Counter()
    for (v, _w), count in coincidence.items():
        value_totals[v] += count
    n = sum(value_totals.values())
    if n == 0:
        return float("nan")

    do = sum(count * delta(v, w) for (v, w), count in coincidence.items()) / n
    de = 0.0
    values = list(value_totals)
    for v in values:
        for w in values:
            if v != w:
                de += value_totals[v] * value_totals[w] * delta(v, w)
    de /= n * (n - 1)

    if de == 0:
        return 1.0 if do == 0 else 0.0
    return 1 - do / de
