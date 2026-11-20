from __future__ import annotations

from pathlib import Path

from pmem.umi.events import EventLog
from pmem.umi.models import TrustInfo
from pmem.umi.versions import ConcurrentModification, VersionStore


def test_event_log_idempotency_and_rollback(tmp_path: Path):
    log = EventLog(tmp_path / "events.sqlite")
    store = VersionStore(log)
    trust = TrustInfo(status="validated", verification="verified")
    s1 = store.commit("mem1", "v1 content about ads", trust=trust, meta={"n": 1}, actor="u", space_key="p")
    assert s1.version == 1
    try:
        store.commit(
            "mem1",
            "v2",
            trust=trust,
            meta={"n": 2},
            actor="u",
            space_key="p",
            expected_version=0,
        )
        assert False, "expected ConcurrentModification"
    except ConcurrentModification:
        pass
    s2 = store.commit("mem1", "v2 merged badly", trust=trust, meta={"n": 2}, actor="u", space_key="p",
                      event_type="merged", expected_version=1)
    rolled = store.rollback("mem1", 1, actor="u", space_key="p")
    assert "v1 content" in rolled.content
    assert rolled.version == s2.version + 1
    log.put_idempotent("k1", "e1", {"ok": True, "id": "mem1"})
    assert log.get_idempotent("k1")["id"] == "mem1"
    assert log.verify_integrity() == []
    log.close()


def test_eval_suite_passes():
    from pmem.umi.eval import run_eval_suite

    suite = run_eval_suite()
    assert suite.ok, suite.as_dict()


def test_audit_candidates_skips_archived():
    from types import SimpleNamespace

    from pmem.umi.governance import audit_candidates

    archived = SimpleNamespace(status="archived", verified=None, extra={"trust": {"status": "candidate"}})
    live = SimpleNamespace(status="seed", verified=None, extra={"trust": {"status": "candidate"}})
    findings = audit_candidates([archived, archived, live])
    assert len(findings) == 1
    assert "1 条" in findings[0].message
