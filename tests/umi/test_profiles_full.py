from __future__ import annotations

from pathlib import Path

import yaml

from pmem.umi.models import SpaceRef, TrustInfo
from pmem.umi.profiles import get_profile, list_profiles
from pmem.umi.profiles.bootstrap import ensure_profile_modules
from pmem.umi.profiles.cross_space import CrossSpaceRequest, evaluate_cross_space
from pmem.umi.profiles.engine import prepare_write
from pmem.service import MemoryService


def test_all_core_and_extension_profiles_registered():
    ids = set(list_profiles())
    for need in (
        "personal", "project", "team", "domain",
        "game", "art", "research", "business", "agent_workflow",
    ):
        assert need in ids
        p = get_profile(need)
        assert p.title
        assert p.as_dict()["id"] == need


def test_personal_preference_maps_kind_and_default_module():
    personal = get_profile("personal")
    prepared = prepare_write(
        personal,
        module="",
        entity="Editor",
        kind="preference",
        content="我偏好在回复里先给结论再给细节，便于快速扫读。",
        layer="memory",
        agent_id="cursor",
    )
    assert prepared.module == "personal.Prefs"
    assert prepared.kind == "conclusion"
    assert prepared.profile_kind == "preference"
    assert not any(i.severity == "error" for i in prepared.issues)


def test_forbid_memory_auto_to_spec():
    team = get_profile("team")
    prepared = prepare_write(
        team,
        module="",
        entity="Review",
        kind="norm",
        content="代码评审必须两人以上通过才能合入主分支，紧急热修除外。",
        layer="spec",
        from_memory_auto=True,
    )
    assert any("禁止由 Memory 自动生成 Spec" in i.message for i in prepared.issues)


def test_cross_space_personal_denied_and_domain_reference_ok():
    req = CrossSpaceRequest(
        mode="reference",
        source_memory_id="m1",
        source=SpaceRef(profile_id="personal", project_id="u1"),
        target=SpaceRef(profile_id="project", project_id="Demo"),
    )
    bad = evaluate_cross_space(
        req, source_profile=get_profile("personal"), target_profile=get_profile("project")
    )
    assert not bad.ok
    assert bad.code == "personal_isolation"

    ok = evaluate_cross_space(
        CrossSpaceRequest(
            mode="reference",
            source_memory_id="m2",
            source=SpaceRef(profile_id="domain", project_id="domain-lib"),
            target=SpaceRef(profile_id="project", project_id="Demo"),
        ),
        source_profile=get_profile("domain"),
        target_profile=get_profile("project"),
    )
    assert ok.ok
    assert ok.link and ok.link["disposition"] == "reference_only"


def test_cursor_cannot_write_spec_without_permission():
    team = get_profile("team")
    prepared = prepare_write(
        team,
        module="",
        entity="Review",
        kind="norm",
        content="代码评审必须两人以上通过才能合入主分支，紧急热修除外。",
        layer="spec",
        agent_id="cursor",
    )
    assert any("无权写入 Spec" in i.message for i in prepared.issues if i.severity == "error")


def test_inbound_disposition_personal_denied():
    from pmem.umi.profiles.cross_space import inbound_disposition

    assert inbound_disposition(
        source_profile_id="personal",
        source_project_id="u1",
        target_profile_id="project",
        target_project_id="Demo",
    ) == "deny"
    assert inbound_disposition(
        source_profile_id="domain",
        source_project_id="lib",
        target_profile_id="project",
        target_project_id="Demo",
    ) == "reference"


def test_bootstrap_and_personal_record(tmp_path: Path):
    memory = tmp_path / ".memory"
    memory.mkdir()
    (memory / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": "DemoUmi", "type": "generic"},
                "vcs": "none",
                "umi": {"enabled": True, "default_profile": "personal", "project_id": "DemoUmi"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (memory / "modules.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "categories": {"personal": {"label": "个人"}},
                "modules": {},
                "synonyms": [],
                "entities": {},
                "third_party": [],
                "ignored": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    added = ensure_profile_modules(tmp_path, "personal")
    assert "personal.Prefs" in added["added"]
    svc = MemoryService(tmp_path)
    try:
        r = svc.controlled_record(
            "",
            "Editor",
            "preference",
            "个人偏好：默认用简体中文回复，代码注释保持原语言。",
            summary="默认简体中文回复",
            profile_id="personal",
            agent_id="cursor",
            op_id="personal_pref_001",
        )
        assert r["ok"], r
        assert r["module"] == "personal.Prefs"
        assert r["umi"]["profile_id"] == "personal"
        assert r["umi"]["profile_kind"] == "preference"
    finally:
        svc.close()
