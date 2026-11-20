"""Personal Profile：个人偏好、习惯、工作方式（与项目权威隔离）。"""
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
        id="personal",
        title="个人偏好与习惯",
        description="只属于当前用户：偏好、习惯、沟通与工作方式。不得写入项目权威 Spec。",
        knowledge_kinds=("preference", "habit", "conclusion", "decision", "exclusion"),
        kind_aliases={"preference": "conclusion", "habit": "decision"},
        required_fields=("entity", "kind", "content"),
        require_module=False,
        default_module="personal.Prefs",
        bootstrap_modules=(
            ("personal.Prefs", "personal/prefs/**"),
            ("personal.Habits", "personal/habits/**"),
        ),
        allowed_layers=("memory", "knowledge"),
        lifecycle=LifecyclePolicy(
            default_trust="candidate",
            auto_promote_on_user_confirm=True,
            max_candidate_age_days=90,
        ),
        allow_authoritative_kinds=("decision", "conclusion"),  # preference→conclusion 后按入库 kind
        write_mode="candidate_first",
        recall_policy="safe",
        doctor_checks=("isolation", "candidates", "integrity"),
        spec_templates=(),
        cross_space=CrossSpacePolicy(
            allow_reference=False,
            allow_adaptation=False,
            allow_copy=False,
            inbound_default="deny",
        ),
        agent_policies={
            "default": AgentPolicy(can_write_candidate=True),
            "cursor": AgentPolicy(can_write_candidate=True),
            "human": AgentPolicy(
                can_write_candidate=True,
                can_promote_validated=True,
                can_promote_authoritative=True,
                can_delete=True,
            ),
        },
        forbid_memory_to_spec_auto=True,
        extra={
            "isolation": "owner_id 必须匹配当前用户",
            "note": "个人空间不得与项目权威知识混写；跨项目默认 deny",
        },
    )
)
