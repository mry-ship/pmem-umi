"""跨空间知识流动：Reference / Adaptation / Copy（须授权）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pmem.umi.events import EventLog
from pmem.umi.models import SpaceRef, new_op_id, to_plain, utc_now_iso
from pmem.umi.profiles.base import Profile, get_profile
from pmem.umi.space import IsolationError, SpaceManager


@dataclass
class CrossSpaceRequest:
    mode: str  # reference / adaptation / copy
    source_memory_id: str
    source: SpaceRef
    target: SpaceRef
    authorized_by: str = ""
    note: str = ""


@dataclass
class CrossSpaceResult:
    ok: bool
    mode: str
    source_memory_id: str
    target_hint: str = ""
    error: str = ""
    code: str = ""
    link: dict[str, Any] | None = None


def evaluate_cross_space(
    req: CrossSpaceRequest,
    *,
    source_profile: Profile,
    target_profile: Profile,
    agent_id: str = "default",
) -> CrossSpaceResult:
    if req.mode not in ("reference", "adaptation", "copy"):
        return CrossSpaceResult(False, req.mode, req.source_memory_id, error="未知跨空间模式", code="mode_invalid")

    policy = target_profile.cross_space
    agent = target_profile.agent(agent_id)

    if req.source.project_id == req.target.project_id and req.source.profile_id == req.target.profile_id:
        return CrossSpaceResult(False, req.mode, req.source_memory_id, error="同源空间无需跨空间操作", code="same_space")

    if req.mode == "reference" and not policy.allow_reference:
        return CrossSpaceResult(False, req.mode, req.source_memory_id, error="目标 Profile 禁止 Reference", code="denied")
    if req.mode == "adaptation" and not policy.allow_adaptation:
        return CrossSpaceResult(False, req.mode, req.source_memory_id, error="目标 Profile 禁止 Adaptation", code="denied")
    if req.mode == "copy":
        if not policy.allow_copy:
            return CrossSpaceResult(False, req.mode, req.source_memory_id, error="目标 Profile 禁止 Copy", code="denied")
        if policy.copy_requires_auth and not (req.authorized_by and agent.can_cross_copy):
            return CrossSpaceResult(
                False, req.mode, req.source_memory_id,
                error="Copy 需要授权人且 Agent 具备 can_cross_copy",
                code="auth_required",
            )

    # personal → 其他默认 deny（已由 personal.cross_space 控制）；再挡一层
    if source_profile.id == "personal" and target_profile.id != "personal":
        return CrossSpaceResult(
            False, req.mode, req.source_memory_id,
            error="个人空间记忆默认不可外泄到其他 Profile",
            code="personal_isolation",
        )

    link = {
        "mode": req.mode,
        "source_memory_id": req.source_memory_id,
        "source": to_plain(req.source),
        "target": to_plain(req.target),
        "authorized_by": req.authorized_by,
        "note": req.note,
        "at": utc_now_iso(),
        "disposition": "reference_only" if req.mode == "reference" else req.mode,
    }
    hint = {
        "reference": "仅引用，不复制为本地事实",
        "adaptation": "须验证后生成本地知识，并保留来源",
        "copy": "授权复制，必须保留 provenance",
    }[req.mode]
    return CrossSpaceResult(True, req.mode, req.source_memory_id, target_hint=hint, link=link)


def record_cross_space_event(log: EventLog, result: CrossSpaceResult, *, actor: str, space_key: str) -> None:
    if not result.ok or not result.link:
        return
    log.append(
        "cross_reference",
        result.link,
        event_id=new_op_id("xspace"),
        memory_id=result.source_memory_id,
        actor=actor,
        space_key=space_key,
    )


def inbound_disposition(
    *,
    source_profile_id: str,
    source_project_id: str,
    target_profile_id: str,
    target_project_id: str,
) -> str:
    """返回 allow / reference / deny。同空间 allow；跨空间按目标 inbound_default；personal 外泄 deny。"""
    same = source_project_id == target_project_id and source_profile_id == target_profile_id
    if same or (not source_project_id and not source_profile_id):
        return "allow"
    if source_profile_id == "personal" and target_profile_id != "personal":
        return "deny"
    profile = get_profile(target_profile_id)
    inbound = profile.cross_space.inbound_default
    if inbound == "deny":
        return "deny"
    if inbound in ("reference", "adaptation", "copy"):
        return "reference"  # 检索侧一律不当本地事实
    return "deny"


def assert_inbound_allowed(spaces: SpaceManager, candidate_space: SpaceRef, target_profile_id: str) -> None:
    """检索侧：外来空间按目标 profile inbound_default 处理，禁止当本地事实。"""
    disp = inbound_disposition(
        source_profile_id=candidate_space.profile_id or "",
        source_project_id=candidate_space.project_id or "",
        target_profile_id=target_profile_id,
        target_project_id=spaces.project_id,
    )
    if disp == "deny":
        raise IsolationError("目标 Profile 拒绝跨空间入站知识", "isolation_violation")
