"""共起ネットワークのグラフ構築と HTML エクスポート（仕様書 3.6）。

ノード径＝コード出現頻度、エッジ太さ＝共起回数。意味的関係（対立/包含/因果）も
エッジとして重ねられる。HTML は vis-network を用い、外部依存なしに自己完結出力する。
NetworkX が導入されていれば `to_networkx` で相互運用も可能。
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field

from shiryo_coder.modules.cooccurrence.cooccurrence import CooccurrenceResult


@dataclass
class GraphNode:
    id: int
    label: str
    value: int                 # 出現頻度（ノード径）
    color: str | None = None


@dataclass
class GraphEdge:
    source: int
    target: int
    weight: float              # 共起回数（エッジ太さ）
    relation: str = "cooccurrence"


@dataclass
class Graph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


def build_graph(
    result: CooccurrenceResult,
    *,
    colors: dict[int, str] | None = None,
    min_count: int = 1,
    relations: list | None = None,
) -> Graph:
    """共起結果（＋任意の意味的関係）からグラフを構築する。"""
    colors = colors or {}
    # 共起エッジに現れるコード、または頻度のあるコードをノード化
    graph = Graph()
    for code_id in result.code_ids:
        graph.nodes.append(
            GraphNode(
                id=code_id,
                label=result.code_names.get(code_id, str(code_id)),
                value=result.frequencies.get(code_id, 0),
                color=colors.get(code_id),
            )
        )
    for (a, b), count in sorted(result.matrix.items()):
        if count >= min_count:
            graph.edges.append(GraphEdge(source=a, target=b, weight=count))
    for rel in relations or []:
        graph.edges.append(
            GraphEdge(
                source=rel.code_a_id, target=rel.code_b_id,
                weight=rel.weight, relation=rel.relation_type,
            )
        )
    return graph


def to_dict(graph: Graph) -> dict:
    """vis-network / 汎用 JSON 形式へ。"""
    return {
        "nodes": [
            {"id": n.id, "label": n.label, "value": max(n.value, 1), "color": n.color}
            for n in graph.nodes
        ],
        "edges": [
            {
                "from": e.source, "to": e.target, "value": e.weight,
                "title": f"{e.relation}: {e.weight}",
                "label": "" if e.relation == "cooccurrence" else e.relation,
            }
            for e in graph.edges
        ],
    }


def to_networkx(graph: Graph):
    """NetworkX グラフへ変換（networkx が必要）。"""
    import networkx as nx

    g = nx.Graph()
    for n in graph.nodes:
        g.add_node(n.id, label=n.label, value=n.value, color=n.color)
    for e in graph.edges:
        g.add_edge(e.source, e.target, weight=e.weight, relation=e.relation)
    return g


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>{title}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>#net{{width:100%;height:90vh;border:1px solid #ddd}}</style></head>
<body><h3>{title}</h3><div id="net"></div>
<script>
const data = {data};
const container = document.getElementById('net');
const options = {{
  nodes: {{ shape: 'dot', scaling: {{ min: 8, max: 48 }}, font: {{ size: 16 }} }},
  edges: {{ scaling: {{ min: 1, max: 12 }}, smooth: false }},
  physics: {{ stabilization: true }}
}};
new vis.Network(container, data, options);
</script></body></html>
"""


def to_html(graph: Graph, *, title: str = "コード共起ネットワーク") -> str:
    """自己完結 HTML（vis-network、CDN 読み込み）を生成する。"""
    data = json.dumps(to_dict(graph), ensure_ascii=False)
    return _HTML_TEMPLATE.format(title=html.escape(title), data=data)
