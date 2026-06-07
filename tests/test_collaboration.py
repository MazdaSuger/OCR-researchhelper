"""共同作業（3.7）のテスト（Qt 非依存）。"""

from __future__ import annotations

import pytest

from shiryo_coder.db import Database
from shiryo_coder.modules.coding import CodebookRepository, CodingRepository
from shiryo_coder.modules.collaboration import (
    AccountRepository,
    ApprovalWorkflow,
    AuditRepository,
    LockRepository,
    PermissionError,
    WorkflowError,
    can,
    export_codings,
    import_codings,
)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "co.db")
    db.initialize()
    pid = db.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    did = db.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, '史料A', '0123456789') RETURNING id",
        (pid,),
    ).fetchone()["id"]
    db.conn.commit()
    yield db, pid, did
    db.close()


# -- アカウント・権限 -----------------------------------------------------------
def test_roles_and_permissions(env):
    db, pid, did = env
    acc = AccountRepository(db)
    admin = acc.create(pid, "主任", role="admin")
    coder = acc.create(pid, "院生", role="coder")
    viewer = acc.create(pid, "見学", role="viewer")

    assert acc.can(admin, "approve") and acc.can(admin, "manage_accounts")
    assert acc.can(coder, "code") and not acc.can(coder, "approve")
    assert acc.can(viewer, "view") and not acc.can(viewer, "code")

    assert can("admin", "approve") and not can("viewer", "code")
    acc.set_role(viewer, "coder")
    assert acc.can(viewer, "code")
    with pytest.raises(PermissionError):
        acc.require(coder, "manage_accounts")


# -- 変更履歴 -------------------------------------------------------------------
def test_audit_history(env):
    db, pid, did = env
    acc = AccountRepository(db)
    coder = acc.create(pid, "A", role="coder")
    audit = AuditRepository(db)
    audit.record(coder, "segment", 1, "create", {"code": "政治"})
    audit.record(coder, "code", 5, "rename", {"from": "x", "to": "y"})

    hist = audit.for_project(pid)
    assert len(hist) == 2
    assert hist[0].action == "rename"               # 新しい順
    assert audit.history(entity="segment")[0].detail["code"] == "政治"


# -- 承認ワークフロー -----------------------------------------------------------
def test_approval_workflow(env):
    db, pid, did = env
    acc = AccountRepository(db)
    admin = acc.create(pid, "主任", role="admin")
    coder = acc.create(pid, "院生", role="coder")
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "政治")
    sid = cd.add_coding(did, code, coder, 0, 5)      # draft

    wf = ApprovalWorkflow(db)
    # コーダーは承認できない
    with pytest.raises(PermissionError):
        wf.approve(sid, coder)
    # 主任が承認 → reviewed → confirmed
    wf.approve(sid, admin)
    assert cd.segments_for_document(did)[0].status == "reviewed"
    wf.confirm(sid, admin)
    assert cd.segments_for_document(did)[0].status == "confirmed"
    # 不正遷移
    with pytest.raises(WorkflowError):
        wf.approve(sid, admin)

    # 監査ログに承認・確定が残る
    assert {e.action for e in AuditRepository(db).for_project(pid)} >= {"approve", "confirm"}


def test_workflow_pending_queues(env):
    db, pid, did = env
    acc = AccountRepository(db)
    admin = acc.create(pid, "主任", role="admin")
    coder = acc.create(pid, "院生", role="coder")
    cb, cd = CodebookRepository(db), CodingRepository(db)
    code = cb.create_code(pid, "X")
    s1 = cd.add_coding(did, code, coder, 0, 3)
    cd.add_coding(did, code, coder, 4, 7)
    wf = ApprovalWorkflow(db)
    assert len(wf.pending(pid, "draft")) == 2
    wf.advance(s1, admin)                            # draft→reviewed
    assert len(wf.pending(pid, "draft")) == 1
    assert wf.pending(pid, "reviewed") == [s1]


# -- ロック ---------------------------------------------------------------------
def test_document_locking(env):
    db, pid, did = env
    acc = AccountRepository(db)
    a = acc.create(pid, "A", role="coder")
    b = acc.create(pid, "B", role="coder")
    lock = LockRepository(db)

    assert lock.acquire(did, a) is True
    assert lock.acquire(did, a) is True              # 本人は再取得 OK
    assert lock.acquire(did, b) is False             # 他者はブロック
    assert lock.release(did, b) is False             # 他者は解放不可
    assert lock.release(did, a) is True
    assert lock.acquire(did, b) is True              # 解放後は取得可
    assert lock.holder(did) == b
    assert len(lock.locks(pid)) == 1


# -- 差分共有（export / import） ------------------------------------------------
def test_sync_export_import_and_conflict(tmp_path):
    # ソース DB
    src = Database(tmp_path / "src.db")
    src.initialize()
    pid_s = src.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    did_s = src.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, '史料A', '0123456789') RETURNING id",
        (pid_s,),
    ).fetchone()["id"]
    src.conn.commit()
    cb, cd = CodebookRepository(src), CodingRepository(src)
    coder = src.conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, '院生') RETURNING id", (pid_s,)
    ).fetchone()["id"]
    src.conn.commit()
    code = cb.create_code(pid_s, "政治")
    cd.add_coding(did_s, code, coder, 0, 5)
    records = export_codings(src, pid_s)
    assert len(records) == 1 and records[0]["doc"] == "史料A"
    src.close()

    # ターゲット DB（同じ文書タイトルあり、コード/コーダーは未作成）
    dst = Database(tmp_path / "dst.db")
    dst.initialize()
    pid_d = dst.conn.execute("INSERT INTO project(name) VALUES ('p') RETURNING id").fetchone()["id"]
    dst.conn.execute(
        "INSERT INTO document(project_id, title, body) VALUES (?, '史料A', '0123456789')", (pid_d,)
    )
    dst.conn.commit()

    report = import_codings(dst, pid_d, records)
    assert report.added == 1 and not report.conflicts
    # 再取り込みは重複せずスキップ
    report2 = import_codings(dst, pid_d, records)
    assert report2.skipped == 1 and report2.added == 0

    # 状態が食い違うとコンフリクト
    changed = [{**records[0], "status": "confirmed"}]
    report3 = import_codings(dst, pid_d, changed)
    assert len(report3.conflicts) == 1
    dst.close()
