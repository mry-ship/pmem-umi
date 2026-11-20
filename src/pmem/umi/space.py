"""Space Manager：Personal / Project / Team / Domain 独立空间与硬隔离。

规则：模型不能绕过 Scope 过滤。跨空间只能 Reference / Adaptation / Copy（经授权）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pmem.umi.models import PROFILES, SpaceRef


class IsolationError(PermissionError):
    """跨空间访问被拒绝。"""

    def __init__(self, message: str, code: str = "isolation_violation"):
        super().__init__(message)
        self.code = code


@dataclass
class SpaceContext:
    """当前请求的隔离上下文：所有读写必须带上。"""

    space: SpaceRef
    agent_id: str = ""
    user_id: str = ""
    allow_cross_reference: bool = False  # 允许 Reference，不允许当本地事实
    recovery_mode: bool = False  # 只读恢复模式

    def assert_writable(self) -> None:
        if self.recovery_mode:
            raise IsolationError("处于 Read-only Recovery Mode，禁止自动写入与整理", "recovery_mode")


@dataclass
class CrossSpaceLink:
    """跨项目经验：引用 / 适配 / 授权复制。"""

    mode: str  # reference / adaptation / copy
    source: SpaceRef
    target: SpaceRef
    memory_id: str
    authorized_by: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ("reference", "adaptation", "copy"):
            raise ValueError("cross-space mode 必须是 reference / adaptation / copy")


@dataclass
class SpaceManager:
    root: Path
    project_id: str
    default_profile: str = "project"
    owner_id: str = ""
    spaces_dir_name: str = "spaces"

    def __post_init__(self) -> None:
        if self.default_profile not in PROFILES:
            raise ValueError(f"profile 必须是 {' / '.join(PROFILES)} 之一")
        self.root = Path(self.root).resolve()

    @classmethod
    def from_config(cls, root: Path | str, config: Any) -> SpaceManager:
        umi = (config.get("umi") if hasattr(config, "get") else None) or {}
        if not isinstance(umi, dict):
            umi = {}
        project = config.get("project") if hasattr(config, "get") else {}
        project = project if isinstance(project, dict) else {}
        name = str(project.get("name") or Path(root).name)
        return cls(
            root=Path(root),
            project_id=str(umi.get("project_id") or name),
            default_profile=str(umi.get("default_profile") or "project"),
            owner_id=str(umi.get("owner_id") or ""),
        )

    def current(self, *, profile: str | None = None, module_id: str = "", entity_id: str = "") -> SpaceRef:
        return SpaceRef(
            profile_id=profile or self.default_profile,
            owner_id=self.owner_id,
            project_id=self.project_id,
            module_id=module_id,
            entity_id=entity_id,
        )

    def context(
        self,
        *,
        profile: str | None = None,
        module_id: str = "",
        entity_id: str = "",
        agent_id: str = "",
        user_id: str = "",
        recovery_mode: bool = False,
    ) -> SpaceContext:
        return SpaceContext(
            space=self.current(profile=profile, module_id=module_id, entity_id=entity_id),
            agent_id=agent_id,
            user_id=user_id or self.owner_id,
            recovery_mode=recovery_mode,
        )

    def same_isolation(self, a: SpaceRef, b: SpaceRef) -> bool:
        return (
            a.profile_id == b.profile_id
            and a.owner_id == b.owner_id
            and a.project_id == b.project_id
        )

    def assert_same_project(self, candidate: SpaceRef, *, allow_reference: bool = False) -> None:
        expected = self.current()
        if candidate.project_id and candidate.project_id != expected.project_id:
            if allow_reference:
                return
            raise IsolationError(
                f"隔离违规：记忆属于项目 {candidate.project_id}，当前是 {expected.project_id}",
                "isolation_violation",
            )
        if candidate.profile_id and candidate.profile_id != expected.profile_id:
            if allow_reference:
                return
            raise IsolationError(
                f"隔离违规：记忆属于 profile {candidate.profile_id}，当前是 {expected.profile_id}",
                "isolation_violation",
            )

    def filter_entries(self, entries: list[Any], ctx: SpaceContext) -> list[Any]:
        """硬过滤：只保留同项目/同 profile 的条目；缺省 space 字段视为本项目（兼容旧记忆）。"""
        out = []
        for entry in entries:
            space = getattr(entry, "space", None) or (entry.extra.get("space") if getattr(entry, "extra", None) else None)
            if not space:
                out.append(entry)
                continue
            ref = space if isinstance(space, SpaceRef) else SpaceRef(**{k: space.get(k, "") for k in (
                "profile_id", "owner_id", "project_id", "module_id", "entity_id"
            ) if isinstance(space, dict)})
            try:
                self.assert_same_project(ref, allow_reference=ctx.allow_cross_reference)
            except IsolationError:
                continue
            if self.same_isolation(ref, ctx.space) or (not ref.project_id and not ref.profile_id):
                out.append(entry)
            elif ctx.allow_cross_reference:
                out.append(entry)
        return out

    def store_path(self, space: SpaceRef) -> Path:
        """多空间物理目录（默认仍用根 .memory；非 project 时分目录）。"""
        base = self.root / ".memory"
        if space.profile_id == "project" and space.project_id in ("", self.project_id):
            return base
        return base / self.spaces_dir_name / space.profile_id / (space.owner_id or "_") / (space.project_id or "_")
