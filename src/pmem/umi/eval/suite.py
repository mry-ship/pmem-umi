"""Memory Evaluation Suite：发布前必跑的隔离 / 时序 / 冲突 / 可追溯 / 演化 / 抗污染测试。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pmem.umi.models import KnowledgeClaim, SpaceRef, TrustInfo
from pmem.umi.safe_recall import SafeRecall
from pmem.umi.space import SpaceManager
from pmem.umi.trust import detect_claim_conflicts, recall_disposition
from pmem.umi.write_gate import WriteGate, WriteRequest


@dataclass
class EvalCase:
    name: str
    category: str
    run: Callable[[], tuple[bool, str]]


@dataclass
class EvalResult:
    name: str
    category: str
    passed: bool
    detail: str


@dataclass
class EvalSuite:
    results: list[EvalResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "results": [
                {"name": r.name, "category": r.category, "passed": r.passed, "detail": r.detail}
                for r in self.results
            ],
        }


def _case_scope_isolation() -> tuple[bool, str]:
    mgr = SpaceManager(root=".", project_id="TileMatch", default_profile="project")
    other = SpaceRef(profile_id="project", project_id="TileStory", module_id="gameplay.X")
    try:
        mgr.assert_same_project(other)
        return False, "应拒绝跨项目"
    except Exception as exc:  # noqa: BLE001
        return "TileStory" in str(exc), str(exc)


def _case_entity_disambiguation() -> tuple[bool, str]:
    left = KnowledgeClaim(subject="Ads", predicate="requires", object="delay")
    right = KnowledgeClaim(subject="Ads", predicate="forbids", object="delay")
    conflicts = detect_claim_conflicts([("a", left, "conclusion")], right)
    return bool(conflicts), f"conflicts={len(conflicts)}"


def _case_temporal_recall() -> tuple[bool, str]:
    old = TrustInfo(status="superseded", verification="verified")
    new = TrustInfo(status="validated", verification="verified")
    return (
        recall_disposition(old) == "reference" and recall_disposition(new) == "allow",
        f"old={recall_disposition(old)} new={recall_disposition(new)}",
    )


def _case_conflict_handling() -> tuple[bool, str]:
    c1 = KnowledgeClaim(subject="GLES", predicate="enabled", object="true")
    c2 = KnowledgeClaim(subject="GLES", predicate="disabled", object="true")
    conflicts = detect_claim_conflicts([("1", c1, "decision")], c2)
    return len(conflicts) >= 1, "ok" if conflicts else "missed conflict"


def _case_evidence_traceability() -> tuple[bool, str]:
    from pmem.umi.models import Evidence

    trust = TrustInfo(
        status="authoritative",
        verification="unverified",
        evidence=[Evidence("inference", note="guess")],
    )
    gate = WriteGate(SpaceManager(root=".", project_id="Demo"))
    from pmem.umi.space import SpaceContext

    req = WriteRequest(
        module="infra.Core",
        entity="Render",
        kind="decision",
        content="项目渲染后端从 GLES3 切换到 Vulkan，需全链路验证。" + ("x" * 20),
        summary="改用 Vulkan",
        trust=trust,
        force_authoritative=False,
    )
    result = gate.check(req, SpaceContext(space=mgr_space()))
    # 应降级或报 evidence
    codes = {i.code for i in result.issues}
    return "evidence" in codes or (result.trust and result.trust.status == "candidate"), str(codes)


def mgr_space():
    return SpaceRef(profile_id="project", project_id="Demo", module_id="infra.Core")


def _case_memory_evolution() -> tuple[bool, str]:
    from pmem.umi.events import EventLog
    from pmem.umi.versions import VersionStore
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(Path(tmp) / "events.sqlite")
        store = VersionStore(log)
        t = TrustInfo(status="validated", verification="verified")
        s1 = store.commit("m1", "原始：低内存关广告", trust=t, meta={"summary": "a"}, actor="t", space_key="p")
        s2 = store.commit(
            "m1",
            "合并后：低内存延迟加载避免锁竞争",
            trust=t,
            meta={"summary": "b", "supersedes_sources": ["a", "b", "c"]},
            actor="t",
            space_key="p",
            event_type="merged",
        )
        rolled = store.rollback("m1", s1.version, actor="t", space_key="p")
        ok = rolled.content.startswith("原始") and s2.version >= 2
        log.close()
        return ok, f"v1={s1.version} v2={s2.version} rolled={rolled.version}"


def _case_cross_session_consistency() -> tuple[bool, str]:
    # 同一 TrustInfo 多次 recall_disposition 应稳定
    t = TrustInfo(status="validated", verification="verified")
    vals = {recall_disposition(t) for _ in range(5)}
    return vals == {"allow"}, str(vals)


def _case_adversarial_recall() -> tuple[bool, str]:
    mgr = SpaceManager(root=".", project_id="TileStory")

    def search_fn(**kwargs):
        return {
            "ok": True,
            "items": [
                {
                    "id": "01HTESTILEMATCH000000000001",
                    "module": "gameplay.X",
                    "status": "active",
                    "summary": "几乎一样的记忆",
                    "trust": {"status": "validated", "verification": "verified"},
                }
            ],
        }

    class E:
        status = "active"
        verified = "2026-01-01"
        extra = {"space": {"profile_id": "project", "project_id": "TileMatch"}}
        content = "x"

    recall = SafeRecall(spaces=mgr, search_fn=search_fn, entry_lookup=lambda _i: E())
    from pmem.umi.space import SpaceContext

    result = recall.recall(SpaceContext(space=mgr.current()), module="gameplay.X", allow_reference=True)
    # 应 reference 而非 allow
    if not result.items:
        return False, "empty"
    return result.items[0].disposition == "reference", result.items[0].disposition


def run_eval_suite() -> EvalSuite:
    cases = [
        EvalCase("Scope Isolation", "isolation", _case_scope_isolation),
        EvalCase("Entity Disambiguation", "entity", _case_entity_disambiguation),
        EvalCase("Temporal Recall", "temporal", _case_temporal_recall),
        EvalCase("Conflict Handling", "conflict", _case_conflict_handling),
        EvalCase("Evidence Traceability", "evidence", _case_evidence_traceability),
        EvalCase("Memory Evolution", "evolution", _case_memory_evolution),
        EvalCase("Cross-session Consistency", "continuity", _case_cross_session_consistency),
        EvalCase("Adversarial Recall", "antipollution", _case_adversarial_recall),
    ]
    suite = EvalSuite()
    for case in cases:
        try:
            passed, detail = case.run()
        except Exception as exc:  # noqa: BLE001
            passed, detail = False, f"exception: {exc}"
        suite.results.append(EvalResult(case.name, case.category, bool(passed), detail))
    return suite
