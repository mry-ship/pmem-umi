"""Project Profile：项目研发工作流（本产品 v0.1 最完整的 Profile）。"""
from __future__ import annotations

from pmem.umi.profiles.base import (
    AgentPolicy,
    CrossSpacePolicy,
    LifecyclePolicy,
    Profile,
    register_profile,
)

register_profile(
    Profile(
        id="project",
        title="项目研发记忆",
        description="按模块沉淀结论：改前检索、改后 Feature/教训、Spec 现状、Doctor/Health。",
        knowledge_kinds=(
            "conclusion",
            "exclusion",
            "correction",
            "risk",
            "decision",
            "feature",
            "plan",
        ),
        required_fields=("module", "entity", "kind", "content"),
        require_module=True,
        allowed_layers=("memory", "knowledge", "spec"),
        lifecycle=LifecyclePolicy(default_trust="candidate", inference_stays_candidate=True),
        allow_authoritative_kinds=("decision", "feature"),
        write_mode="candidate_first",
        recall_policy="safe",
        doctor_checks=("isolation", "integrity", "candidates", "drift", "conflicts", "spec", "temporal"),
        spec_templates=("策划设计.md", "程序设计.md", "美术设计.md", "现状.md"),
        cross_space=CrossSpacePolicy(
            allow_reference=True,
            allow_adaptation=True,
            allow_copy=False,
            inbound_default="reference",
        ),
        agent_policies={
            "default": AgentPolicy(can_write_candidate=True),
            "cursor": AgentPolicy(can_write_candidate=True, can_propose=True),
            "claude": AgentPolicy(can_write_candidate=True, can_propose=True),
            "codex": AgentPolicy(can_write_candidate=True, can_propose=True),
            "human": AgentPolicy(
                can_propose=True,
                can_write_candidate=True,
                can_promote_validated=True,
                can_promote_authoritative=True,
                can_merge=True,
                can_cross_copy=True,
                can_edit_spec=True,
                can_delete=True,
            ),
        },
        extra={
            "workflow": [
                "改代码前按模块检索",
                "改后写 feature / 教训",
                "Spec 维护现状",
                "Doctor / Health / Report",
            ]
        },
    )
)
