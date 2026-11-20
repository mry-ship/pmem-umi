"""可插拔 Profile 协议：引擎只执行规则，不理解行业语义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Memory=经历与事实；Knowledge=验证后的知识；Spec=当前应遵守的规范（不可互相替代）
KNOWLEDGE_LAYERS = ("memory", "knowledge", "spec")

_REGISTRY: dict[str, "Profile"] = {}


@dataclass
class AgentPolicy:
    """不同 Agent 的权限：模型只是执行器，规则引擎管权限。"""

    can_propose: bool = True
    can_write_candidate: bool = True
    can_promote_validated: bool = False
    can_promote_authoritative: bool = False
    can_merge: bool = False
    can_cross_copy: bool = False
    can_edit_spec: bool = False
    can_delete: bool = False


@dataclass
class CrossSpacePolicy:
    allow_reference: bool = True
    allow_adaptation: bool = False
    allow_copy: bool = False
    copy_requires_auth: bool = True
    # domain 知识进入 project 时默认只能 reference
    inbound_default: str = "reference"  # reference / adaptation / copy / deny


@dataclass
class LifecyclePolicy:
    default_trust: str = "candidate"
    auto_promote_on_user_confirm: bool = True
    max_candidate_age_days: int = 30
    allow_observation_only: bool = True
    # 推理派生不得自动升为事实
    inference_stays_candidate: bool = True


@dataclass
class Profile:
    id: str
    title: str
    description: str = ""
    # 对外知识类型（可含 preference 等；入库时经 kind_aliases 映射到 Entry.KINDS）
    knowledge_kinds: tuple[str, ...] = ()
    kind_aliases: dict[str, str] = field(default_factory=dict)
    required_fields: tuple[str, ...] = ("entity", "kind", "content")
    require_module: bool = True
    default_module: str = ""
    bootstrap_modules: tuple[tuple[str, str], ...] = ()  # (module_id, paths_glob)
    allowed_layers: tuple[str, ...] = ("memory", "knowledge")
    lifecycle: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    allow_authoritative_kinds: tuple[str, ...] = ("decision",)
    write_mode: str = "candidate_first"
    recall_policy: str = "safe"
    doctor_checks: tuple[str, ...] = ("isolation", "integrity", "candidates")
    spec_templates: tuple[str, ...] = ()
    agent_policies: dict[str, AgentPolicy] = field(default_factory=dict)
    cross_space: CrossSpacePolicy = field(default_factory=CrossSpacePolicy)
    # Spec 不得由 Memory 自动生成
    forbid_memory_to_spec_auto: bool = True
    validate: Callable[[dict[str, Any]], list[str]] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_policies:
            self.agent_policies = {
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
            }

    def resolve_kind(self, kind: str) -> tuple[str, str]:
        """返回 (入库 Entry.kind, 原始 profile_kind)。"""
        raw = (kind or "").strip()
        if raw in self.kind_aliases:
            return self.kind_aliases[raw], raw
        return raw, raw

    def agent(self, agent_id: str = "default") -> AgentPolicy:
        return self.agent_policies.get(agent_id) or self.agent_policies.get("default") or AgentPolicy()

    def run_validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if self.validate:
            errors.extend(self.validate(payload) or [])
        for f in self.required_fields:
            if self.require_module is False and f == "module":
                continue
            if not payload.get(f):
                errors.append(f"缺少字段 {f}")
        kind = str(payload.get("kind") or "")
        profile_kind = str(payload.get("profile_kind") or kind)
        allowed = set(self.knowledge_kinds) | set(self.kind_aliases)
        if self.knowledge_kinds and profile_kind and profile_kind not in allowed and kind not in self.knowledge_kinds:
            errors.append(f"profile {self.id} 不支持 kind={profile_kind!r}")
        layer = str(payload.get("layer") or "memory")
        if layer not in self.allowed_layers:
            errors.append(f"profile {self.id} 不允许 layer={layer!r}（允许 {', '.join(self.allowed_layers)}）")
        if layer == "spec" and self.forbid_memory_to_spec_auto and payload.get("from_memory_auto"):
            errors.append("禁止由 Memory 自动生成 Spec；须人工确认后写入")
        return errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "knowledge_kinds": list(self.knowledge_kinds),
            "kind_aliases": dict(self.kind_aliases),
            "required_fields": list(self.required_fields),
            "require_module": self.require_module,
            "default_module": self.default_module,
            "bootstrap_modules": [list(x) for x in self.bootstrap_modules],
            "allowed_layers": list(self.allowed_layers),
            "lifecycle": {
                "default_trust": self.lifecycle.default_trust,
                "auto_promote_on_user_confirm": self.lifecycle.auto_promote_on_user_confirm,
                "max_candidate_age_days": self.lifecycle.max_candidate_age_days,
                "inference_stays_candidate": self.lifecycle.inference_stays_candidate,
            },
            "allow_authoritative_kinds": list(self.allow_authoritative_kinds),
            "write_mode": self.write_mode,
            "recall_policy": self.recall_policy,
            "doctor_checks": list(self.doctor_checks),
            "spec_templates": list(self.spec_templates),
            "cross_space": {
                "allow_reference": self.cross_space.allow_reference,
                "allow_adaptation": self.cross_space.allow_adaptation,
                "allow_copy": self.cross_space.allow_copy,
                "copy_requires_auth": self.cross_space.copy_requires_auth,
                "inbound_default": self.cross_space.inbound_default,
            },
            "forbid_memory_to_spec_auto": self.forbid_memory_to_spec_auto,
            "agents": {
                k: {
                    "can_propose": v.can_propose,
                    "can_write_candidate": v.can_write_candidate,
                    "can_promote_validated": v.can_promote_validated,
                    "can_promote_authoritative": v.can_promote_authoritative,
                    "can_merge": v.can_merge,
                    "can_cross_copy": v.can_cross_copy,
                    "can_edit_spec": v.can_edit_spec,
                    "can_delete": v.can_delete,
                }
                for k, v in self.agent_policies.items()
            },
            "extra": dict(self.extra),
        }


def register_profile(profile: Profile) -> Profile:
    _REGISTRY[profile.id] = profile
    return profile


def get_profile(profile_id: str) -> Profile:
    if profile_id not in _REGISTRY:
        raise KeyError(f"未知 profile：{profile_id}；已注册：{', '.join(sorted(_REGISTRY))}")
    return _REGISTRY[profile_id]


def list_profiles() -> list[str]:
    return sorted(_REGISTRY)


def all_profiles() -> list[Profile]:
    return [get_profile(i) for i in list_profiles()]
