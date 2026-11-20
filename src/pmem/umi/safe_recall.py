"""Safe Recall：先保证正确，再追求召回率。

顺序：身份 → Profile/项目 → 模块/实体 → 硬隔离 → 混合检索 → 状态/证据/有效期 → 排除冲突 → 组装。
模型不能绕过 Scope 过滤。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pmem.umi.models import TrustInfo
from pmem.umi.profiles.cross_space import inbound_disposition
from pmem.umi.space import IsolationError, SpaceContext, SpaceManager
from pmem.umi.trust import parse_trust, recall_disposition


@dataclass
class RecallItem:
    id: str
    module: str
    disposition: str  # allow / reference / withhold
    trust: TrustInfo
    reason: str = ""
    cross_space: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecallResult:
    ok: bool
    items: list[RecallItem] = field(default_factory=list)
    withheld: list[RecallItem] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "safe_recall": True,
            "items": [
                {
                    **i.payload,
                    "id": i.id,
                    "module": i.module,  # 强制覆盖 payload，避免空/错 module 冲掉 Safe Recall 字段
                    "disposition": i.disposition,
                    "trust_status": i.trust.status,
                    "verification": i.trust.verification,
                    "reason": i.reason,
                    "cross_space": i.cross_space,
                }
                for i in self.items
            ],
            "withheld": [
                {"id": i.id, "module": i.module, "reason": i.reason, "disposition": i.disposition}
                for i in self.withheld
            ],
            "refusals": list(self.refusals),
            **({"code": self.code} if self.code else {}),
        }


@dataclass
class SafeRecall:
    spaces: SpaceManager
    search_fn: Callable[..., dict[str, Any]]
    entry_lookup: Callable[[str], Any] | None = None

    def recall(
        self,
        ctx: SpaceContext,
        *,
        module: str | None = None,
        path: str | None = None,
        entity: str | None = None,
        query: str | None = None,
        limit: int | None = None,
        when: dict | None = None,
        as_of: str | None = None,
        allow_reference: bool = True,
        source_conversation: str | None = None,
        full: bool = False,
        ids: list[str] | None = None,
    ) -> RecallResult:
        # 1–2. 身份与空间已在 ctx
        ctx.allow_cross_reference = allow_reference

        # 3–4. 先硬隔离：禁止无空间上下文的裸搜
        if not ctx.space.project_id:
            return RecallResult(
                ok=False,
                refusals=["未确定当前项目空间，拒绝检索"],
                code="scope_missing",
            )

        # 5. 混合检索（底层仍用现有 index；此处加安全过滤）
        try:
            raw = self.search_fn(
                module=module,
                path=path,
                entity=entity,
                query=query,
                limit=limit,
                source_conversation=source_conversation,
                as_of=as_of,
                full=full,
                ids=ids,
                when=when,
            )
        except Exception as exc:  # noqa: BLE001
            return RecallResult(ok=False, refusals=[str(exc)], code="search_error")

        if not raw.get("ok"):
            return RecallResult(
                ok=False,
                refusals=[str(raw.get("error") or "检索失败")],
                code=raw.get("code"),
            )

        items_out: list[RecallItem] = []
        withheld: list[RecallItem] = []
        refusals: list[str] = []

        for row in list(raw.get("items") or []) + list(raw.get("features") or []):
            if not isinstance(row, dict) or not row.get("id"):
                continue
            mem_id = str(row["id"])
            entry = self.entry_lookup(mem_id) if self.entry_lookup else None
            space_meta = {}
            legacy_status = str(row.get("status") or "active")
            verified = bool(row.get("verified") or (getattr(entry, "verified", None) if entry else None))
            if entry is not None:
                extra = getattr(entry, "extra", {}) or {}
                space_meta = extra.get("space") if isinstance(extra.get("space"), dict) else {}
                trust = parse_trust(extra, legacy_status=entry.status, verified=bool(entry.verified))
            else:
                trust = parse_trust(row.get("trust") if isinstance(row.get("trust"), dict) else {},
                                    legacy_status=legacy_status, verified=verified)

            # 硬隔离 + 目标 Profile inbound_default
            cross = False
            src_profile = str(space_meta.get("profile_id") or "")
            src_project = str(space_meta.get("project_id") or "")
            inbound = inbound_disposition(
                source_profile_id=src_profile,
                source_project_id=src_project,
                target_profile_id=ctx.space.profile_id or "project",
                target_project_id=ctx.space.project_id or "",
            )
            if inbound != "allow":
                cross = True
                if inbound == "deny" or not allow_reference:
                    withheld.append(
                        RecallItem(
                            id=mem_id,
                            module=str(row.get("module") or ""),
                            disposition="withhold",
                            trust=trust,
                            reason="跨空间隔离：目标 Profile 拒绝入站或不可作本空间事实",
                            cross_space=True,
                        )
                    )
                    continue
                disposition = "reference"
                reason = "跨空间相似记忆，仅作参考（Reference）"
            else:
                disposition = recall_disposition(trust)
                reason = ""

            # 6–7. 状态 / 证据 / 过期
            if row.get("stale"):
                if disposition == "allow":
                    disposition = "reference"
                    reason = reason or "记忆已过期/需核实，不作为当前结论"
            if trust.status == "rejected":
                disposition = "withhold"
                reason = "已拒绝的推论/记忆"
            if row.get("conflict"):
                disposition = "withhold"
                reason = "存在未解决冲突"
                refusals.append(f"{mem_id}: 未解决冲突")

            module_name = str(row.get("module") or (getattr(entry, "module", None) if entry else None) or "")
            item = RecallItem(
                id=mem_id,
                module=module_name,
                disposition=disposition,
                trust=trust,
                reason=reason,
                cross_space=cross,
                payload={k: v for k, v in row.items() if k not in ("content",) or disposition == "allow"},
            )
            if module_name and not item.payload.get("module"):
                item.payload["module"] = module_name
            # reference 去掉正文，避免模型当事实用
            if disposition == "reference":
                item.payload = {
                    k: v for k, v in row.items()
                    if k in ("id", "module", "entity", "kind", "summary", "date", "status", "applies", "when")
                }
                item.payload["reference_only"] = True
                items_out.append(item)
            elif disposition == "allow":
                items_out.append(item)
            else:
                withheld.append(item)

        if not items_out and not withheld:
            refusals.append("没有找到可靠依据")
        elif not items_out and withheld:
            refusals.append("仅有不适用/未验证/已拒绝记忆，已拒答")

        return RecallResult(ok=True, items=items_out, withheld=withheld, refusals=refusals)

    def assert_module_scope(self, ctx: SpaceContext, module: str) -> None:
        """改代码前闸门可调用：确保当前空间下的模块检索。"""
        if not module:
            raise IsolationError("缺少模块，无法安全召回", "scope_missing")
        ctx.space.module_id = module
