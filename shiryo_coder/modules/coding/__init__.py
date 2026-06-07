"""3.3 コーディングモジュール（中核機能）。

責務:
- コードブック（無制限階層ツリー、HSL 自動配色、定義・包含/除外基準、XML 取り込み）
- 範囲選択コーディング（重複・部分重なり許容、積層レイアウト）
- メモ・注釈（3 階層）、ジャーナル
- AI 支援コーディング（類似セグメント検索 → 候補提示、承認制）

公開 API:
- `CodebookRepository`, `CodeNode`, `CycleError`
- `CodingRepository`, `CodedSegment`, `assign_layers`
- `MemoRepository`, `Memo`
- `suggest_codes`, `CharNGramEmbedder`, `Suggestion`
- `parse_codebook_xml`, `import_codebook`
- `auto_color`
"""

from shiryo_coder.modules.coding.codebook import CodebookRepository, CodeNode, CycleError
from shiryo_coder.modules.coding.codebook_import import import_codebook, parse_codebook_xml
from shiryo_coder.modules.coding.coding import CodedSegment, CodingRepository, assign_layers
from shiryo_coder.modules.coding.colors import auto_color
from shiryo_coder.modules.coding.memos import Memo, MemoRepository
from shiryo_coder.modules.coding.suggest import CharNGramEmbedder, Suggestion, suggest_codes

__all__ = [
    "CodebookRepository",
    "CodeNode",
    "CycleError",
    "CodingRepository",
    "CodedSegment",
    "assign_layers",
    "MemoRepository",
    "Memo",
    "suggest_codes",
    "CharNGramEmbedder",
    "Suggestion",
    "parse_codebook_xml",
    "import_codebook",
    "auto_color",
]
