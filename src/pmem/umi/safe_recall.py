"""Safe Recall：先保证正确，再追求召回率。

顺序：身份 → Profile/项目 → 模块/实体 → 硬隔离 → 混合检索 → 状态/证据/有效期 → 排除冲突 → 组装。
模型不能绕过 Scope 过滤。

依赖 MemoryRetriever / TrustManager 端口，不依赖 pmem.Entry。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pmem.umi.core.ports import MemoryRetriever, TrustManager
from pmem.umi.core.types import MemoryHit, MemoryRecord, RetrieveResult
from pmem.umi.models import TrustInfo
from pmem.umi.profiles.cross_space import inbound_disposition
from pmem.umi.space import IsolationError, SpaceContext, SpaceManager
from pmem.umi.trust import DefaultTrustManager, parse_trust, recall_disposition


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
    retriever: MemoryRetriever | None = None
    trust_manager: TrustManager | None = None
    # 兼容旧调用：无 retriever 时用 search_fn + entry_lookup
    search_fn: Callable[..., dict[str, Any]] | None = None
    entry_lookup: Callable[[str], Any] | None = None

    def _trust_of(self, hit: MemoryHit, record: MemoryRecord | None = None) -> TrustInfo:
        tm = self.trust_manager or DefaultTrustManager()
        if hit.trust is not None:
            return hit.trust
        if record is not None:
            return tm.parse(record)
        return parse_trust(
            hit.payload.get("trust") if isinstance(hit.payload.get("trust"), dict) else {},
            legacy_status=hit.status,
            verified=hit.verified,
        )

    def _retrieve(self, **kwargs) -> RetrieveResult:
        if self.retriever is not None:
            return self.retriever.search(**kwargs)
        if self.search_fn is None:
            return RetrieveResult(ok=False, error="未配置 MemoryRetriever", code="retriever_missing")
        try:
            raw = self.search_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return RetrieveResult(ok=False, error=str(exc), code="search_error")
        if not raw.get("ok"):
            return RetrieveResult(
                ok=False,
                error=str(raw.get("error") or "检索失败"),
                code=raw.get("code"),
                raw=raw,
            )
        hits: list[MemoryHit] = []
        for row in list(raw.get("items") or []) + list(raw.get("features") or []):
            if not isinstance(row, dict) or not row.get("id"):
                continue
            hits.append(
                MemoryHit(
                    id=str(row["id"]),
                    module=str(row.get("module") or ""),
                    entity=str(row.get("entity") or ""),
                    kind=str(row.get("kind") or ""),
                    summary=str(row.get("summary") or ""),
                    status=str(row.get("status") or "active"),
                    verified=bool(row.get("verified")),
                    stale=bool(row.get("stale")),
                    conflict=bool(row.get("conflict")),
                    payload=dict(row),
                )
            )
        return RetrieveResult(ok=True, hits=hits, raw=raw)

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
        ctx.allow_cross_reference = allow_reference

        if not ctx.space.project_id:
            return RecallResult(
                ok=False,
                refusals=["未确定当前项目空间，拒绝检索"],
                code="scope_missing",
            )

        result = self._retrieve(
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
        if not result.ok:
            return RecallResult(ok=False, refusals=[result.error or "检索失败"], code=result.code)

        tm = self.trust_manager or DefaultTrustManager()
        items_out: list[RecallItem] = []
        withheld: list[RecallItem] = []
        refusals: list[str] = []

        for hit in list(result.hits) + list(result.features):
            record = None
            if self.entry_lookup:
                raw_entry = self.entry_lookup(hit.id)
                if raw_entry is not None and hasattr(raw_entry, "extra"):
                    extra = getattr(raw_entry, "extra", None) or {}
                    # 完整 Entry 才走 Adapter 转换；评测/桩对象只取 space/trust
                    if getattr(raw_entry, "id", None) and getattr(raw_entry, "module", None) is not None:
                        from pmem.umi.adapters.pmem import entry_to_record

                        record = entry_to_record(raw_entry)
                        if not hit.module:
                            hit.module = record.module
                        if hit.trust is None:
                            hit.trust = record.trust
                        if hit.space is None:
                            hit.space = record.space
                    else:
                        if hit.trust is None:
                            hit.trust = parse_trust(
                                extra,
                                legacy_status=str(getattr(raw_entry, "status", hit.status) or "active"),
                                verified=bool(getattr(raw_entry, "verified", False)),
                            )
                        if hit.space is None and isinstance(extra.get("space"), dict):
                            from pmem.umi.models import SpaceRef

                            sp = extra["space"]
                            hit.space = SpaceRef(
                                profile_id=str(sp.get("profile_id") or ""),
                                project_id=str(sp.get("project_id") or ""),
                                module_id=str(sp.get("module_id") or ""),
                                entity_id=str(sp.get("entity_id") or ""),
                            )

            trust = self._trust_of(hit, record)
            space_meta = {}
            if hit.space is not None:
                space_meta = {
                    "profile_id": hit.space.profile_id,
                    "project_id": hit.space.project_id,
                }
            elif record and record.space:
                space_meta = {
                    "profile_id": record.space.profile_id,
                    "project_id": record.space.project_id,
                }
            elif isinstance(hit.payload.get("space"), dict):
                space_meta = hit.payload["space"]

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
                            id=hit.id,
                            module=hit.module,
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
                disposition = tm.disposition(trust)
                reason = ""

            if hit.stale:
                if disposition == "allow":
                    disposition = "reference"
                    reason = reason or "记忆已过期/需核实，不作为当前结论"
            if trust.status == "rejected":
                disposition = "withhold"
                reason = "已拒绝的推论/记忆"
            if hit.conflict:
                disposition = "withhold"
                reason = "存在未解决冲突"
                refusals.append(f"{hit.id}: 未解决冲突")

            module_name = hit.module or ""
            row = hit.payload or {
                "id": hit.id,
                "module": module_name,
                "entity": hit.entity,
                "kind": hit.kind,
                "summary": hit.summary,
                "status": hit.status,
            }
            item = RecallItem(
                id=hit.id,
                module=module_name,
                disposition=disposition,
                trust=trust,
                reason=reason,
                cross_space=cross,
                payload={k: v for k, v in row.items() if k not in ("content",) or disposition == "allow"},
            )
            if module_name and not item.payload.get("module"):
                item.payload["module"] = module_name
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
        if not module:
            raise IsolationError("缺少模块，无法安全召回", "scope_missing")
        ctx.space.module_id = module
