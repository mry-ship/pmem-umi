"""Team Profile：团队规范、共享约定、协作经验。"""
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
        id="team",
        title="团队规范与共享经验",
        description="团队级约定与可复用经验。团队规范升权威须人工授权（L3）。",
        knowledge_kinds=("conclusion", "exclusion", "risk", "decision", "norm", "playbook"),
        kind_aliases={"norm": "decision", "playbook": "conclusion"},
        required_fields=("entity", "kind", "content"),
        require_module=False,
        default_module="team.Norms",
        bootstrap_modules=(
            ("team.Norms", "team/norms/**"),
            ("team.Playbook", "team/playbook/**"),
        ),
        allowed_layers=("memory", "knowledge", "spec"),
        lifecycle=LifecyclePolicy(default_trust="candidate", inference_stays_candidate=True),
        allow_authoritative_kinds=("decision", "norm"),
        write_mode="candidate_first",
        recall_policy="safe",
        doctor_checks=("isolation", "integrity", "conflicts", "drift", "candidates", "spec"),
        spec_templates=("团队规范.md", "协作约定.md", "现状.md"),
        cross_space=CrossSpacePolicy(
            allow_reference=True,
            allow_adaptation=True,
            allow_copy=False,
            inbound_default="reference",
        ),
        agent_policies={
            "default": AgentPolicy(can_write_candidate=True),
            "cursor": AgentPolicy(can_write_candidate=True, can_propose=True),
            "human": AgentPolicy(
                can_write_candidate=True,
                can_promote_validated=True,
                can_promote_authoritative=True,
                can_merge=True,
                can_edit_spec=True,
                can_delete=True,
            ),
        },
        extra={"promotion": "团队规范升 authoritative 必须 human + force"},
    )
)
