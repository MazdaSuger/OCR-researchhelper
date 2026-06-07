"""3.6 共起・関係性可視化モジュール。

責務:
- 共起マトリクス（同一セグメント=重なり / 同一段落 / 距離 N 文字以内）
- ネットワーク図（ノード径=頻度、エッジ太さ=共起、HTML エクスポート）
- コード間関係の手動定義（対立 / 包含 / 因果）
- ヒートマップ（年代×コード、著者×コード 等）
- 時系列（年代に基づくコード出現頻度推移）

公開 API:
- `CooccurrenceRepository`, `CooccurrenceResult`
- `RelationRepository`, `CodeRelation`
- `build_graph`, `to_html`, `to_dict`, `to_networkx`, `Graph`
- `HeatmapRepository`, `CrossTab`
"""

from shiryo_coder.modules.cooccurrence.cooccurrence import (
    CooccurrenceRepository,
    CooccurrenceResult,
)
from shiryo_coder.modules.cooccurrence.heatmap import CrossTab, HeatmapRepository
from shiryo_coder.modules.cooccurrence.network import (
    Graph,
    build_graph,
    to_dict,
    to_html,
    to_networkx,
)
from shiryo_coder.modules.cooccurrence.relations import CodeRelation, RelationRepository

__all__ = [
    "CooccurrenceRepository",
    "CooccurrenceResult",
    "RelationRepository",
    "CodeRelation",
    "build_graph",
    "to_html",
    "to_dict",
    "to_networkx",
    "Graph",
    "HeatmapRepository",
    "CrossTab",
]
