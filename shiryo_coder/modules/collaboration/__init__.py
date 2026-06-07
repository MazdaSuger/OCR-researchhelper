"""3.7 共同作業モジュール。

責務:
- コーダーアカウント管理（管理者/コーダー/閲覧者）と役割ベース権限
- 変更履歴（誰がいつどのセグメントに何をしたか: audit_log）
- 承認ワークフロー（下書き → 主任承認 → 確定）
- ロック方式（document_lock による同時編集の排他制御）
- 差分共有（コーディングの export/import、コンフリクト報告）

公開 API:
- `AccountRepository`, `Account`, `can`, `PermissionError`, `ROLES`
- `AuditRepository`, `AuditEntry`
- `ApprovalWorkflow`, `WorkflowError`
- `LockRepository`, `Lock`
- `export_codings`, `import_codings`, `ImportReport`, `export_to_file`
"""

from shiryo_coder.modules.collaboration.accounts import (
    ROLES,
    Account,
    AccountRepository,
    PermissionError,
    can,
)
from shiryo_coder.modules.collaboration.audit import AuditEntry, AuditRepository
from shiryo_coder.modules.collaboration.locks import Lock, LockRepository
from shiryo_coder.modules.collaboration.sync import (
    ImportReport,
    export_codings,
    export_to_file,
    import_codings,
)
from shiryo_coder.modules.collaboration.workflow import ApprovalWorkflow, WorkflowError

__all__ = [
    "AccountRepository",
    "Account",
    "can",
    "PermissionError",
    "ROLES",
    "AuditRepository",
    "AuditEntry",
    "ApprovalWorkflow",
    "WorkflowError",
    "LockRepository",
    "Lock",
    "export_codings",
    "import_codings",
    "export_to_file",
    "ImportReport",
]
