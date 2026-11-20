"""按当前 Profile 执行写入/召回/权限规则。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pmem.umi.profiles.base import Profile, get_profile
from pmem.umi.trust import TrustInfo, promotion_risk
from pmem.umi.write_gate import GateIssue, WriteRequest


@dataclass
class PreparedWrite:
    module: str
    kind: str
    profile_kind: str
    layer: str
    trust: TrustInfo
    issues: list[GateIssue]
    profile: Profile


def prepare_write(
    profile: Profile,
    *,
    module: str,
    entity: str,
    kind: str,
    content: str,
    layer: str = "memory",
    trust: TrustInfo | None = None,
    agent_id: str = "default",
    from_memory_auto: bool = False,
    evidence_types: list[str] | None = None,
) -> PreparedWrite:
    issues: list[GateIssue] = []
    agent = profile.agent(agent_id)
    if not agent.can_write_candidate and not agent.can_promote_validated:
        issues.append(GateIssue("permission", f"Agent {agent_id} 无权写入该 Profile", "error"))

    entry_kind, profile_kind = profile.resolve_kind(kind)
    mod = (module or "").strip() or profile.default_module
    payload = {
        "module": mod,
        "entity": entity,
        "kind": entry_kind,
        "profile_kind": profile_kind,
        "content": content,
        "layer": layer or "memory",
        "from_memory_auto": from_memory_auto,
    }
    for msg in profile.run_validate(payload):
        issues.append(GateIssue("profile", msg, "error"))

    if profile.require_module and not mod:
        issues.append(GateIssue("ownership", "当前 Profile 要求 module", "error"))

    layer_norm = str(layer or "memory")
    if layer_norm == "spec" and not agent.can_edit_spec:
        issues.append(GateIssue("permission", f"Agent {agent_id} 无权写入 Spec（需 can_edit_spec）", "error"))

    trust = trust or TrustInfo(status=profile.lifecycle.default_trust)
    # 推理证据不得自动升格
    if profile.lifecycle.inference_stays_candidate and evidence_types:
        if "inference" in evidence_types and trust.status in ("validated", "authoritative"):
            issues.append(GateIssue("evidence", "推理派生不得自动升为已验证/权威，已降级 candidate", "warn"))
            trust = TrustInfo(status="candidate", verification="unverified", evidence=list(trust.evidence))

    if profile.write_mode == "candidate_first" and trust.status in ("validated", "authoritative"):
        if not agent.can_promote_validated and trust.status == "validated":
            issues.append(GateIssue("authority", "Agent 不能直接写 validated，降级 candidate", "warn"))
            trust = TrustInfo(status="candidate", verification="unverified", evidence=list(trust.evidence))
        if trust.status == "authoritative" and not agent.can_promote_authoritative:
            issues.append(GateIssue("authority", "Agent 不能直接写 authoritative，降级 candidate", "warn"))
            trust = TrustInfo(status="candidate", verification="unverified", evidence=list(trust.evidence))

    return PreparedWrite(
        module=mod,
        kind=entry_kind,
        profile_kind=profile_kind,
        layer=layer_norm,
        trust=trust,
        issues=issues,
        profile=profile,
    )


def profile_risk(profile: Profile, kind: str, trust_status: str, *, is_spec: bool = False) -> str:
    if is_spec or trust_status == "authoritative":
        return "L3"
    if kind in profile.allow_authoritative_kinds and trust_status == "validated":
        return "L2"
    return promotion_risk(trust_status, is_spec=is_spec, is_decision=kind == "decision")


def apply_profile_to_gate_request(req: WriteRequest, prepared: PreparedWrite) -> WriteRequest:
    req.module = prepared.module
    req.kind = prepared.kind
    req.trust = prepared.trust
    req.is_spec = prepared.layer == "spec"
    return req


def current_profile(config: Any) -> Profile:
    umi = (config.get("umi") if hasattr(config, "get") else None) or {}
    if not isinstance(umi, dict):
        umi = {}
    return get_profile(str(umi.get("default_profile") or "project"))
