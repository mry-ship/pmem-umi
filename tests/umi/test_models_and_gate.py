from __future__ import annotations

from pmem.umi.models import KnowledgeClaim, TrustInfo, content_hash, legacy_status_for_trust
from pmem.umi.space import SpaceContext, SpaceManager, SpaceRef
from pmem.umi.trust import detect_claim_conflicts, recall_disposition
from pmem.umi.write_gate import WriteGate, WriteRequest


def test_legacy_status_mapping():
    assert legacy_status_for_trust("candidate") == "seed"
    assert legacy_status_for_trust("validated") == "active"
    assert legacy_status_for_trust("authoritative") == "active"
    assert legacy_status_for_trust("archived") == "archived"


def test_isolation_blocks_cross_project():
    mgr = SpaceManager(root=".", project_id="A")
    try:
        mgr.assert_same_project(SpaceRef(project_id="B", profile_id="project"))
        assert False, "should raise"
    except Exception as exc:
        assert "隔离" in str(exc)


def test_write_gate_rejects_short_and_unverified_authority():
    gate = WriteGate(SpaceManager(root=".", project_id="Demo"))
    ctx = SpaceContext(space=SpaceRef(project_id="Demo", profile_id="project"))
    bad = gate.check(
        WriteRequest(module="infra.Core", entity="X", kind="conclusion", content="太短", summary="x"),
        ctx,
    )
    assert not bad.ok
    assert any(i.code == "value" for i in bad.issues)

    auth = gate.check(
        WriteRequest(
            module="infra.Core",
            entity="Render",
            kind="decision",
            content="项目决定切换到 Vulkan 后端，需要全平台验证通过后才可合并。" + ("。" * 5),
            summary="改用 Vulkan",
            trust=TrustInfo(status="authoritative", verification="unverified"),
        ),
        ctx,
    )
    assert auth.ok  # 降级为 candidate，警告而非硬失败
    assert auth.trust and auth.trust.status == "candidate"


def test_claim_conflict_and_recall_disposition():
    left = KnowledgeClaim(subject="WebView", predicate="causes", object="ANR")
    right = KnowledgeClaim(subject="WebView", predicate="not_causes", object="ANR")
    conflicts = detect_claim_conflicts([("1", left, "conclusion")], right)
    assert conflicts
    assert recall_disposition(TrustInfo(status="validated", verification="verified")) == "allow"
    assert recall_disposition(TrustInfo(status="candidate", verification="unverified")) == "reference"
    assert content_hash("a") != content_hash("b")
