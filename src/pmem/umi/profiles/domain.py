"""Domain Profile：跨项目领域知识；进入项目默认只能 Reference/Adaptation。"""
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
        id="domain",
        title="领域通用知识",
        description="跨项目可复用的领域模式与约束。复制到项目须授权；默认 reference。",
        knowledge_kinds=("conclusion", "exclusion", "risk", "decision", "pattern", "constraint"),
        kind_aliases={"pattern": "conclusion", "constraint": "risk"},
        required_fields=("entity", "kind", "content"),
        require_module=False,
        default_module="domain.Patterns",
        bootstrap_modules=(
            ("domain.Patterns", "domain/patterns/**"),
            ("domain.Constraints", "domain/constraints/**"),
        ),
        allowed_layers=("memory", "knowledge"),
        lifecycle=LifecyclePolicy(default_trust="candidate", max_candidate_age_days=180),
        allow_authoritative_kinds=("decision", "constraint"),
        write_mode="candidate_first",
        recall_policy="safe",
        doctor_checks=("isolation", "integrity", "conflicts", "candidates"),
        spec_templates=(),
        cross_space=CrossSpacePolicy(
            allow_reference=True,
            allow_adaptation=True,
            allow_copy=True,
            copy_requires_auth=True,
            inbound_default="reference",
        ),
        agent_policies={
            "default": AgentPolicy(can_write_candidate=True),
            "cursor": AgentPolicy(can_write_candidate=True, can_propose=True),
            "human": AgentPolicy(
                can_write_candidate=True,
                can_promote_validated=True,
                can_promote_authoritative=True,
                can_cross_copy=True,
                can_merge=True,
                can_delete=True,
            ),
        },
        extra={"cross_space": "reference_or_adaptation_default; copy needs auth"},
    )
)
