"""UMI Core 端口：业务依赖 Protocol，pmem 只作为 Adapter。"""
from __future__ import annotations

from pathlib import Path

import yaml

from pmem.service import MemoryService
from pmem.umi.adapters.pmem import build_pmem_runtime, entry_to_record
from pmem.umi.core import (
    GovernanceEngine,
    KnowledgeRepository,
    MemoryRetriever,
    MemoryStore,
    TrustManager,
)
from pmem.umi.core.types import MemoryRecord
from pmem.umi.models import TrustInfo


def _init(tmp_path: Path) -> Path:
    memory = tmp_path / ".memory"
    memory.mkdir()
    (memory / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": "PortsDemo", "type": "generic"},
                "vcs": "none",
                "umi": {"enabled": True, "default_profile": "project", "project_id": "PortsDemo"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (memory / "modules.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "categories": {"infra": {"label": "infra"}},
                "modules": {"infra.Core": {"paths": ["src/**"]}},
                "synonyms": [],
                "entities": {},
                "third_party": [],
                "ignored": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def test_build_pmem_runtime_satisfies_protocols(tmp_path: Path):
    root = _init(tmp_path)
    svc = MemoryService(root)
    try:
        rt = build_pmem_runtime(svc)
        assert isinstance(rt.store, MemoryStore)
        assert isinstance(rt.retriever, MemoryRetriever)
        assert isinstance(rt.knowledge, KnowledgeRepository)
        assert isinstance(rt.trust, TrustManager)
        assert isinstance(rt.governance, GovernanceEngine)

        written = svc.controlled_record(
            "infra.Core",
            "Ports",
            "decision",
            "UMI 业务只依赖端口，换底层只换 Adapter，不重写隔离与信任逻辑。",
            summary="端口优先于 pmem 内部类型",
            op_id="ports_demo_001",
        )
        assert written["ok"], written
        mid = written["id"]
        record = rt.store.get(mid)
        assert isinstance(record, MemoryRecord)
        assert record.module == "infra.Core"
        assert record.trust is not None

        # core.types 不得被 Entry 污染：MemoryRecord 无 Entry 字段约定以外的内部 API
        assert not hasattr(record, "note_date") or "note_date" not in MemoryRecord.__dataclass_fields__

        promoted = svc.promote_memory(
            mid,
            to_status="validated",
            evidence=[{"evidence_type": "user_confirm", "verified": True}],
        )
        assert promoted["ok"], promoted
        again = rt.store.get(mid)
        assert again is not None
        assert again.trust is not None
        assert again.trust.status == "validated"
    finally:
        svc.close()


def test_entry_to_record_only_in_adapter():
    """Adapter 边界：转换函数存在，但 MemoryRecord 可独立构造。"""
    rec = MemoryRecord(
        id="x",
        module="infra.Core",
        entity="E",
        kind="decision",
        content="独立构造，不经过 Entry。",
        trust=TrustInfo(status="candidate"),
    )
    assert rec.id == "x"
    assert callable(entry_to_record)
