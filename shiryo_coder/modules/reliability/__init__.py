"""3.5 信頼性検証モジュール（複数コーダー一致率）。

責務:
- Cohen's κ（2 コーダー）/ Fleiss' κ・Krippendorff's α（3 名以上）
- 算出単位: 文字 / 文 / セグメント
- 不一致セグメント抽出（協議用 CSV エクスポート）
- コーダー研修モード（マスターとの逐次フィードバック）

公開 API:
- 係数: `cohens_kappa`, `fleiss_kappa`, `krippendorff_alpha`
- 高水準: `ReliabilityRepository`, `ReliabilityResult`, `Disagreement`,
  `TrainingFeedback`, `disagreements_to_csv`, `GRANULARITIES`
"""

from shiryo_coder.modules.reliability.agreement import (
    cohens_kappa,
    fleiss_kappa,
    krippendorff_alpha,
)
from shiryo_coder.modules.reliability.reliability import (
    GRANULARITIES,
    Disagreement,
    ReliabilityRepository,
    ReliabilityResult,
    TrainingFeedback,
    disagreements_to_csv,
)

__all__ = [
    "cohens_kappa",
    "fleiss_kappa",
    "krippendorff_alpha",
    "ReliabilityRepository",
    "ReliabilityResult",
    "Disagreement",
    "TrainingFeedback",
    "disagreements_to_csv",
    "GRANULARITIES",
]
