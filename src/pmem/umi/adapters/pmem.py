"""pmem Adapter：用现有 Index / FilesStorage / VersionStore / SearchOps 实现 UMI 端口。

UMI 业务不得 import Entry；本文件是唯一允许把 Entry ↔ MemoryRecord 互转的地方。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pmem.umi.core.runtime import UmiRuntime
from pmem.umi.core.types import MemoryHit, MemoryRecord, RetrieveResult
from pmem.umi.governance import run_governance
from pmem.umi.models import KnowledgeClaim, Provenance, SpaceRef, TrustInfo, content_hash
from pmem.umi.space import SpaceManager
from pmem.umi.trust import parse_claim, parse_trust, promotion_risk, recall_disposition
from pmem.umi.versions import VersionStore


def _space_from_extra(extra: dict[str, Any] | None) -> SpaceRef | None:
    extra = extra or {}
    raw = extra.get("space")
    if not isinstance(raw, dict):
        return None
    return SpaceRef(
        profile_id=str(raw.get("profile_id") or "project"),
        owner_id=str(raw.get("owner_id") or ""),
        project_id=str(raw.get("project_id") or ""),
        module_id=str(raw.get("module_id") or ""),
        entity_id=str(raw.get("entity_id") or ""),
    )


def entry_to_record(entry: Any) -> MemoryRecord:
    """Entry → MemoryRecord（仅 Adapter 调用）。"""
    extra = getattr(entry, "extra", None) or {}
    trust = parse_trust(extra, legacy_status=entry.status, verified=bool(entry.verified))
    claim = parse_claim(extra)
    prov_raw = extra.get("provenance") if isinstance(extra.get("provenance"), dict) else None
    provenance = None
    if prov_raw:
        provenance = Provenance(
            source_type=str(prov_raw.get("source_type") or "conversation"),
            source_id=str(prov_raw.get("source_id") or ""),
            extracted_by=str(prov_raw.get("extracted_by") or ""),
            recorded_by=str(prov_raw.get("recorded_by") or ""),
        )
    return MemoryRecord(
        id=entry.id,
        module=entry.module,
        entity=entry.entity,
        kind=entry.kind,
        content=entry.content,
        summary=getattr(entry, "title", None) or getattr(entry, "summary", None) or "",
        status=entry.status,
        verified=bool(entry.verified),
        trust=trust,
        space=_space_from_extra(extra),
        claim=claim if claim and not claim.is_empty() else None,
        provenance=provenance,
        version=int(extra.get("version") or 0),
        layer=str(extra.get("layer") or "memory"),
        profile_id=str(extra.get("profile_id") or (extra.get("space") or {}).get("profile_id") or ""),
        profile_kind=str(extra.get("profile_kind") or ""),
        content_sha256=str(extra.get("content_sha256") or ""),
        anchors=list(getattr(entry, "anchors", None) or []),
        aliases=list(getattr(entry, "aliases", None) or []),
        applies=str(getattr(entry, "applies", None) or ""),
        when=dict(getattr(entry, "when", None) or {}),
        supersedes=list(getattr(entry, "supersedes", None) or []),
        source_conversation=str(getattr(entry, "source_conversation", None) or ""),
        author=str(getattr(entry, "author", None) or ""),
        extra=dict(extra),
    )


def record_to_entry_overlay(record: MemoryRecord) -> dict[str, Any]:
    """把 UMI 字段写回 Entry.extra。"""
    from pmem.umi.models import to_plain
    from pmem.umi.trust import trust_to_meta

    overlay = dict(record.extra or {})
    if record.trust is not None:
        overlay["trust"] = trust_to_meta(record.trust)
    if record.space is not None:
        overlay["space"] = to_plain(record.space)
    if record.claim is not None and not record.claim.is_empty():
        overlay["claim"] = to_plain(record.claim)
    if record.provenance is not None:
        overlay["provenance"] = to_plain(record.provenance)
    overlay["version"] = record.version
    overlay["layer"] = record.layer
    overlay["profile_id"] = record.profile_id
    overlay["profile_kind"] = record.profile_kind
    overlay["content_sha256"] = record.content_sha256 or content_hash(record.content)
    return overlay


def _hit_from_row(row: dict[str, Any], record: MemoryRecord | None = None) -> MemoryHit:
    trust = record.trust if record else None
    space = record.space if record else None
    if trust is None and isinstance(row.get("trust"), dict):
        trust = parse_trust({"trust": row["trust"]}, legacy_status=str(row.get("status") or "active"))
    return MemoryHit(
        id=str(row.get("id") or ""),
        module=str(row.get("module") or (record.module if record else "") or ""),
        entity=str(row.get("entity") or (record.entity if record else "") or ""),
        kind=str(row.get("kind") or (record.kind if record else "") or ""),
        summary=str(row.get("summary") or ""),
        status=str(row.get("status") or (record.status if record else "active") or "active"),
        verified=bool(row.get("verified") or (record.verified if record else False)),
        stale=bool(row.get("stale")),
        conflict=bool(row.get("conflict")),
        trust=trust,
        space=space,
        score=float(row.get("score") or 0.0),
        payload=dict(row),
    )


@dataclass
class PmemMemoryStore:
    """基于 pmem Index + FilesStorage。"""

    index: Any
    storage: Any

    def get(self, memory_id: str) -> MemoryRecord | None:
        self.index.refresh(force=False)
        entry = self.index.find(memory_id)
        return entry_to_record(entry) if entry is not None else None

    def list(
        self,
        *,
        module: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[MemoryRecord]:
        self.index.refresh(force=True)
        out: list[MemoryRecord] = []
        for entry in self.index.entries():
            if module and entry.module != module:
                continue
            if statuses and entry.status not in statuses:
                continue
            out.append(entry_to_record(entry))
        return out

    def save(self, record: MemoryRecord) -> MemoryRecord:
        entry = self.index.find(record.id)
        if entry is None:
            raise KeyError(f"记忆不存在：{record.id}")
        entry.content = record.content
        entry.status = record.status
        entry.extra = record_to_entry_overlay(record)
        if record.summary:
            entry.summary = record.summary
        path = self.storage.find_path(entry.id)
        if path:
            self.storage.rewrite(path, entry)
            self.index.refresh(force=True)
        return entry_to_record(entry)


@dataclass
class PmemMemoryRetriever:
    """基于 SearchOps.search；结果转成 MemoryHit，并尽量补全 trust/space。"""

    search_fn: Any
    store: PmemMemoryStore

    def search(
        self,
        *,
        module: str | None = None,
        path: str | None = None,
        entity: str | None = None,
        query: str | None = None,
        limit: int | None = None,
        when: dict | None = None,
        as_of: str | None = None,
        full: bool = False,
        ids: list[str] | None = None,
        source_conversation: str | None = None,
    ) -> RetrieveResult:
        try:
            raw = self.search_fn(
                module=module,
                path=path,
                entity=entity,
                query=query,
                limit=limit,
                when=when,
                as_of=as_of,
                full=full,
                ids=ids,
                source_conversation=source_conversation,
            )
        except Exception as exc:  # noqa: BLE001
            return RetrieveResult(ok=False, error=str(exc), code="search_error")
        if not raw.get("ok"):
            return RetrieveResult(
                ok=False,
                error=str(raw.get("error") or "检索失败"),
                code=raw.get("code"),
                raw=raw if isinstance(raw, dict) else {},
            )
        hits: list[MemoryHit] = []
        features: list[MemoryHit] = []
        for row in list(raw.get("items") or []):
            if not isinstance(row, dict) or not row.get("id"):
                continue
            rec = self.store.get(str(row["id"]))
            hits.append(_hit_from_row(row, rec))
        for row in list(raw.get("features") or []):
            if not isinstance(row, dict) or not row.get("id"):
                continue
            rec = self.store.get(str(row["id"]))
            features.append(_hit_from_row(row, rec))
        return RetrieveResult(ok=True, hits=hits, features=features, raw=raw)


@dataclass
class PmemKnowledgeRepository:
    versions: VersionStore
    event_log: Any

    def commit(
        self,
        memory_id: str,
        content: str,
        *,
        trust: TrustInfo,
        meta: dict[str, Any],
        actor: str,
        space_key: str,
        op_id: str,
        event_type: str = "updated",
        expected_version: int | None = None,
    ) -> Any:
        return self.versions.commit(
            memory_id,
            content,
            trust=trust,
            meta=meta,
            actor=actor,
            space_key=space_key,
            op_id=op_id,
            event_type=event_type,
            expected_version=expected_version,
        )

    def rollback(
        self,
        memory_id: str,
        to_version: int,
        *,
        actor: str,
        space_key: str,
        op_id: str,
    ) -> Any:
        return self.versions.rollback(
            memory_id, to_version, actor=actor, space_key=space_key, op_id=op_id
        )

    def latest_version(self, memory_id: str) -> int:
        return self.event_log.latest_version(memory_id)


@dataclass
class PmemTrustManager:
    def parse(self, record: MemoryRecord) -> TrustInfo:
        if record.trust is not None:
            return record.trust
        return parse_trust(
            record.extra,
            legacy_status=record.status,
            verified=record.verified,
        )

    def disposition(self, trust: TrustInfo) -> str:
        return recall_disposition(trust)

    def promotion_risk(
        self, trust_status: str, *, is_spec: bool = False, is_decision: bool = False
    ) -> str:
        return promotion_risk(trust_status, is_spec=is_spec, is_decision=is_decision)


@dataclass
class PmemGovernanceEngine:
    root: Path

    def report(
        self,
        records: list[MemoryRecord],
        *,
        spaces: SpaceManager,
        recovery_mode: bool = False,
        doctor_checks: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        # governance 仍用 duck-typing；用轻量代理避免 Entry 依赖泄漏到 ports
        proxies = [_RecordProxy(r) for r in records]
        report = run_governance(
            self.root,
            proxies,
            spaces=spaces,
            recovery_mode=recovery_mode,
            doctor_checks=doctor_checks,
        )
        return report.as_dict()


@dataclass
class _RecordProxy:
    """把 MemoryRecord 伪装成 governance 期望的 entry 形状。"""

    _r: MemoryRecord

    @property
    def id(self) -> str:
        return self._r.id

    @property
    def module(self) -> str:
        return self._r.module

    @property
    def kind(self) -> str:
        return self._r.kind

    @property
    def content(self) -> str:
        return self._r.content

    @property
    def status(self) -> str:
        return self._r.status

    @property
    def verified(self) -> bool:
        return self._r.verified

    @property
    def author(self) -> str:
        return self._r.author

    @property
    def source_conversation(self) -> str:
        return self._r.source_conversation

    @property
    def extra(self) -> dict[str, Any]:
        return record_to_entry_overlay(self._r)


@dataclass
class PmemAdapter:
    """一次性装配六大端口。"""

    runtime: UmiRuntime


def build_pmem_runtime(service: Any) -> UmiRuntime:
    """从 MemoryService（或具备 index/storage/event_log/spaces 的对象）装配 Runtime。"""
    from pmem.service.search import SearchOps

    store = PmemMemoryStore(index=service.index, storage=service.storage)
    retriever = PmemMemoryRetriever(
        search_fn=lambda **kw: SearchOps.search(service, **kw),
        store=store,
    )
    log = service.event_log()
    knowledge = PmemKnowledgeRepository(versions=VersionStore(log), event_log=log)
    spaces = service.spaces()
    return UmiRuntime(
        store=store,
        retriever=retriever,
        knowledge=knowledge,
        trust=PmemTrustManager(),
        spaces=spaces,
        governance=PmemGovernanceEngine(root=Path(service.root)),
    )
