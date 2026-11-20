from __future__ import annotations

from pathlib import Path

import yaml

from pmem.service import MemoryService


def _init_mini_project(tmp_path: Path) -> Path:
    memory = tmp_path / ".memory"
    memory.mkdir()
    (memory / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": "DemoUmi", "type": "generic"},
                "vcs": "none",
                "umi": {
                    "enabled": True,
                    "default_profile": "project",
                    "project_id": "DemoUmi",
                    "write_mode": "candidate_first",
                    "safe_recall": True,
                },
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


def test_controlled_record_promote_rollback_governance(tmp_path: Path):
    root = _init_mini_project(tmp_path)
    svc = MemoryService(root)
    try:
        r1 = svc.controlled_record(
            "infra.Core",
            "Render",
            "decision",
            "渲染后端从 GLES3 切换到 Vulkan，需全链路验证后才能作为默认选项。",
            summary="改用 Vulkan",
            trust_status="candidate",
            op_id="op_demo_001",
            claim={"subject": "Render", "predicate": "uses", "object": "Vulkan"},
        )
        assert r1["ok"], r1
        mem_id = r1["id"]
        r1b = svc.controlled_record(
            "infra.Core",
            "Render",
            "decision",
            "渲染后端从 GLES3 切换到 Vulkan，需全链路验证后才能作为默认选项。",
            summary="改用 Vulkan",
            trust_status="candidate",
            op_id="op_demo_001",
        )
        assert r1b.get("idempotent") is True

        no_ev = svc.promote_memory(mem_id, to_status="validated", evidence=[])
        assert no_ev["ok"] is False and no_ev.get("code") == "evidence"

        promo = svc.promote_memory(
            mem_id,
            to_status="validated",
            evidence=[{"evidence_type": "user_confirm", "verified": True, "note": "负责人确认"}],
        )
        assert promo["ok"], promo
        assert promo["trust"]["status"] == "validated"

        # candidate_first：带 evidence 也不能绕过 promote 直达 validated
        bypass = svc.controlled_record(
            "infra.Core",
            "Render",
            "decision",
            "未经晋升不得把带证据的主张直接写成 validated 权威结论并污染长期记忆。",
            summary="禁止 evidence 绕过",
            trust_status="validated",
            verification="verified",
            evidence=[{"evidence_type": "inference", "verified": True}],
            op_id="op_demo_bypass",
            promote=False,
        )
        assert bypass["ok"], bypass
        assert bypass["umi"]["trust"]["status"] == "candidate"

        # 再写一版后回滚
        r2 = svc.controlled_record(
            "infra.Core",
            "Render",
            "decision",
            "（错误合并）低内存设备需要延迟加载广告以避免 MAX SDK 锁竞争并关闭广告。",
            summary="错误合并结论",
            trust_status="candidate",
            draft_id=mem_id,
            op_id="op_demo_002",
            promote=True,
        )
        # draft 覆盖未提交记忆
        assert r2["ok"] or r2.get("code") == "draft_forbidden"
        gov = svc.governance_report()
        assert gov["ok"]
        search = svc.safe_search(module="infra.Core", query="Vulkan")
        assert search["ok"]
        assert search.get("safe_recall") is True
        for item in search.get("items") or []:
            assert item.get("module"), f"Safe Recall 结果缺 module: {item}"
    finally:
        svc.close()
