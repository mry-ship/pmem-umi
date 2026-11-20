"""行业扩展 Profile：注册即用，不改引擎。"""
from __future__ import annotations

from pmem.umi.profiles.base import (
    AgentPolicy,
    CrossSpacePolicy,
    LifecyclePolicy,
    Profile,
    register_profile,
)


def register_extensions() -> list[str]:
    specs = [
        Profile(
            id="game",
            title="游戏研发",
            description="玩法、数值、广告、崩溃与设备差异等游戏项目知识。",
            knowledge_kinds=("conclusion", "exclusion", "correction", "risk", "decision", "feature", "plan"),
            required_fields=("module", "entity", "kind", "content"),
            require_module=True,
            allowed_layers=("memory", "knowledge", "spec"),
            lifecycle=LifecyclePolicy(),
            doctor_checks=("isolation", "integrity", "conflicts", "drift", "candidates", "spec"),
            spec_templates=("策划设计.md", "程序设计.md", "美术设计.md", "现状.md"),
            cross_space=CrossSpacePolicy(allow_reference=True, allow_adaptation=True),
            extra={"extends": "project"},
        ),
        Profile(
            id="art",
            title="美术生产",
            description="风格约束、产能、资源规范、审核标准。",
            knowledge_kinds=("conclusion", "exclusion", "decision", "style", "pipeline"),
            kind_aliases={"style": "decision", "pipeline": "conclusion"},
            required_fields=("entity", "kind", "content"),
            require_module=False,
            default_module="art.Style",
            bootstrap_modules=(("art.Style", "art/style/**"), ("art.Pipeline", "art/pipeline/**")),
            allowed_layers=("memory", "knowledge", "spec"),
            doctor_checks=("isolation", "candidates", "spec"),
            spec_templates=("风格规范.md", "产出标准.md", "现状.md"),
            cross_space=CrossSpacePolicy(allow_reference=True, allow_adaptation=True),
        ),
        Profile(
            id="research",
            title="研究与实验",
            description="假设、实验记录、结论与可复现约束；推测默认保持 candidate。",
            knowledge_kinds=("conclusion", "exclusion", "risk", "decision", "hypothesis", "experiment"),
            kind_aliases={"hypothesis": "plan", "experiment": "conclusion"},
            required_fields=("entity", "kind", "content"),
            require_module=False,
            default_module="research.Notes",
            bootstrap_modules=(("research.Notes", "research/notes/**"),),
            allowed_layers=("memory", "knowledge"),
            lifecycle=LifecyclePolicy(inference_stays_candidate=True, max_candidate_age_days=365),
            doctor_checks=("integrity", "candidates", "conflicts", "evidence"),
            cross_space=CrossSpacePolicy(allow_reference=True, allow_copy=False),
            extra={"note": "hypothesis 不得自动升 authoritative"},
        ),
        Profile(
            id="business",
            title="业务与运营",
            description="业务规则、指标口径、活动约束；权威变更须人工。",
            knowledge_kinds=("conclusion", "decision", "risk", "metric", "campaign"),
            kind_aliases={"metric": "conclusion", "campaign": "feature"},
            required_fields=("entity", "kind", "content"),
            require_module=False,
            default_module="business.Rules",
            bootstrap_modules=(("business.Rules", "business/rules/**"),),
            allowed_layers=("memory", "knowledge", "spec"),
            allow_authoritative_kinds=("decision",),
            doctor_checks=("isolation", "integrity", "conflicts", "candidates", "spec"),
            spec_templates=("业务规则.md", "指标口径.md", "现状.md"),
            agent_policies={
                "default": AgentPolicy(can_write_candidate=True),
                "human": AgentPolicy(
                    can_write_candidate=True,
                    can_promote_validated=True,
                    can_promote_authoritative=True,
                    can_edit_spec=True,
                    can_delete=True,
                ),
            },
        ),
        Profile(
            id="agent_workflow",
            title="Agent 工作流",
            description="多 Agent 协作约定、工具权限、回合策略；不替代项目事实。",
            knowledge_kinds=("conclusion", "decision", "risk", "exclusion", "workflow"),
            kind_aliases={"workflow": "decision"},
            required_fields=("entity", "kind", "content"),
            require_module=False,
            default_module="agent.Workflow",
            bootstrap_modules=(("agent.Workflow", "agent/workflow/**"),),
            allowed_layers=("memory", "knowledge", "spec"),
            doctor_checks=("isolation", "candidates", "integrity"),
            spec_templates=("Agent约定.md", "工具权限.md"),
            cross_space=CrossSpacePolicy(allow_reference=True, inbound_default="reference"),
            extra={"note": "工作流记忆不得绕过 Space 硬隔离"},
        ),
    ]
    ids = []
    for p in specs:
        register_profile(p)
        ids.append(p.id)
    return ids
