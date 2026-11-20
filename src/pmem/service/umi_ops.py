"""UMI 受控写入 / 安全召回 / 晋升 / 回滚 —— 挂到 MemoryService。"""
from __future__ import annotations

from pmem.core.ids import new_ulid
from pmem.service.base import ServiceBase, fail, returns_errors
from pmem.service.record import RecordOps
from pmem.service.search import SearchOps
from pmem.umi.events import EventLog, event_log_path
from pmem.umi.governance import is_recovery_mode, set_recovery_mode
from pmem.umi.models import (
    Evidence,
    KnowledgeClaim,
    Provenance,
    TrustInfo,
    content_hash,
    legacy_status_for_trust,
    new_op_id,
    to_plain,
    valid_op_id,
)
from pmem.umi.profiles import get_profile
from pmem.umi.safe_recall import SafeRecall
from pmem.umi.space import SpaceManager
from pmem.umi.trust import parse_claim, parse_trust
from pmem.umi.versions import VersionStore, entry_meta_overlay
from pmem.umi.write_gate import WriteGate, WriteRequest


class UmiOps(ServiceBase):
    _event_log: EventLog | None = None
    _spaces: SpaceManager | None = None
    _umi_runtime: object | None = None

    def umi_enabled(self) -> bool:
        umi = self.config.get("umi") or {}
        return bool(umi.get("enabled", True))

    def write_mode(self) -> str:
        umi = self.config.get("umi") or {}
        mode = str(umi.get("write_mode") or "").strip()
        if mode in ("candidate_first", "legacy"):
            return mode
        profile = get_profile(umi.get("default_profile") or "project")
        return profile.write_mode

    def spaces(self) -> SpaceManager:
        if self._spaces is None:
            self._spaces = SpaceManager.from_config(self.root, self.config)
        return self._spaces

    def event_log(self) -> EventLog:
        if self._event_log is None:
            self._event_log = EventLog(event_log_path(self.root))
        return self._event_log

    def umi_runtime(self):
        """UMI Core 运行时：业务应经此拿 Store/Retriever/…，避免直接绑 pmem 内部类型。"""
        if self._umi_runtime is None:
            from pmem.umi.adapters.pmem import build_pmem_runtime

            self._umi_runtime = build_pmem_runtime(self)
        return self._umi_runtime

    def close(self) -> None:
        if self._event_log is not None:
            self._event_log.close()
            self._event_log = None
        self._umi_runtime = None
        super().close()

    def _ctx(self, module: str = "", entity: str = "", source_conversation: str | None = None):
        recovery = is_recovery_mode(self.root) or bool((self.config.get("umi") or {}).get("recovery_mode"))
        return self.spaces().context(
            module_id=module,
            entity_id=entity,
            user_id=self.user,
            recovery_mode=recovery,
        )

    def _existing_summaries(self, module: str) -> list[str]:
        self.index.refresh(force=True)
        out = []
        for e in self.index.entries():
            if e.module == module and e.status in ("active", "seed", "draft"):
                out.append(e.title)
        return out

    def _existing_claims(self, module: str) -> list[tuple[str, KnowledgeClaim | None, str]]:
        self.index.refresh(force=True)
        rows = []
        for e in self.index.entries():
            if e.module == module and e.status in ("active", "seed", "draft"):
                rows.append((e.id, parse_claim(e.extra or {}), e.kind))
        return rows

    @returns_errors
    def safe_search(self, **kwargs) -> dict:
        if not self.umi_enabled():
            return SearchOps.search(self, **kwargs)
        module = kwargs.get("module") or ""
        ctx = self._ctx(module=module or "")
        rt = self.umi_runtime()
        recall = SafeRecall(
            spaces=self.spaces(),
            retriever=rt.retriever,
            trust_manager=rt.trust,
        )
        result = recall.recall(ctx, **kwargs)
        data = result.as_dict()
        data["module"] = kwargs.get("module") or (data["items"][0]["module"] if data["items"] else None)
        return data

    def active_profile(self):
        from pmem.umi.profiles.engine import current_profile

        return current_profile(self.config)

    def controlled_record(
        self,
        module: str,
        entity: str,
        kind: str,
        content: str,
        *,
        summary: str | None = None,
        trust_status: str = "candidate",
        verification: str = "unverified",
        evidence: list[dict] | None = None,
        claim: dict | None = None,
        op_id: str | None = None,
        expected_version: int | None = None,
        draft_id: str | None = None,
        supersedes: list[str] | None = None,
        anchors: list[str] | None = None,
        aliases: list[str] | None = None,
        applies: str | None = None,
        when: dict | None = None,
        verify: str | None = None,
        scope: str | None = None,
        enforced_by: list[str] | None = None,
        source_conversation: str | None = None,
        force_authoritative: bool = False,
        promote: bool = False,
        layer: str = "memory",
        agent_id: str = "default",
        profile_id: str | None = None,
    ) -> dict:
        if not self.umi_enabled():
            return RecordOps.record(
                self, module, entity, kind, content,
                supersedes=supersedes, anchors=anchors, draft_id=draft_id,
                source_conversation=source_conversation, aliases=aliases, summary=summary,
                applies=applies, when=when, verify=verify, scope=scope, enforced_by=enforced_by,
            )
        return self._controlled_record(
            module, entity, kind, content, summary, trust_status, verification, evidence,
            claim, op_id, expected_version, draft_id, supersedes, anchors, aliases, applies, when,
            verify, scope, enforced_by, source_conversation, force_authoritative, promote,
            layer, agent_id, profile_id,
        )

    @returns_errors
    def _controlled_record(
        self, module, entity, kind, content, summary, trust_status, verification, evidence,
        claim, op_id, expected_version, draft_id, supersedes, anchors, aliases, applies, when,
        verify, scope, enforced_by, source_conversation, force_authoritative, promote,
        layer="memory", agent_id="default", profile_id=None,
    ) -> dict:
        from pmem.umi.models import WriteOpId
        from pmem.umi.profiles.bootstrap import ensure_profile_modules
        from pmem.umi.profiles.engine import prepare_write

        profile = get_profile(profile_id) if profile_id else self.active_profile()
        ensure_profile_modules(self.root, profile.id)

        try:
            op = valid_op_id(op_id) or new_op_id("write")
        except ValueError as exc:
            return fail(str(exc), "op_id")

        ev_objs: list[Evidence] = []
        try:
            for item in evidence or []:
                if isinstance(item, dict) and item.get("evidence_type"):
                    ev_objs.append(
                        Evidence(
                            evidence_type=str(item["evidence_type"]),
                            source_id=str(item.get("source_id") or ""),
                            note=str(item.get("note") or ""),
                            verified=bool(item.get("verified")),
                        )
                    )
        except ValueError as exc:
            return fail(str(exc), "evidence")

        trust = TrustInfo(status=trust_status, verification=verification, evidence=ev_objs)
        if self.write_mode() == "candidate_first" and not promote:
            if trust.status == "authoritative" and force_authoritative:
                pass
            elif trust.status in ("validated", "authoritative"):
                trust = TrustInfo(status="candidate", verification="unverified", evidence=ev_objs)

        prepared = prepare_write(
            profile,
            module=module or "",
            entity=entity,
            kind=kind,
            content=content,
            layer=layer or "memory",
            trust=trust,
            agent_id=agent_id or "default",
            evidence_types=[e.evidence_type for e in ev_objs],
        )
        if any(i.severity == "error" for i in prepared.issues):
            return fail(
                "; ".join(i.message for i in prepared.issues if i.severity == "error"),
                "profile",
                issues=[i.__dict__ for i in prepared.issues],
            )
        module = prepared.module
        kind = prepared.kind
        trust = prepared.trust
        # force authoritative 且 human/agent 允许时保留
        if force_authoritative and trust_status == "authoritative" and profile.agent(agent_id).can_promote_authoritative:
            trust = TrustInfo(status="authoritative", verification=verification, evidence=ev_objs)
        # promote / force 直达高信任时仍须核实证据（与 promote_memory 对齐）
        if trust.status in ("validated", "authoritative") and not any(e.verified for e in trust.evidence):
            return fail("写入已验证/权威等级需要至少一条已核实证据（evidence_type + verified）", "evidence")

        ctx = self._ctx(module=module, entity=entity, source_conversation=source_conversation)
        ctx.space.profile_id = profile.id
        ctx.space.module_id = module
        ctx.space.entity_id = entity

        claim_obj = None
        if isinstance(claim, dict):
            claim_obj = KnowledgeClaim(
                subject=str(claim.get("subject") or ""),
                predicate=str(claim.get("predicate") or ""),
                object=str(claim.get("object") or ""),
            )
            if claim_obj.is_empty():
                claim_obj = None

        log = self.event_log()
        op_key = WriteOpId(op_id=op, space=ctx.space, intent="record").key()
        cached = log.get_idempotent(op_key)
        if cached:
            return {**cached, "idempotent": True}

        gate = WriteGate(
            self.spaces(),
            existing_claims=self._existing_claims,
            existing_summaries=self._existing_summaries,
        )
        req = WriteRequest(
            module=module,
            entity=entity,
            kind=kind,
            content=content,
            summary=summary or "",
            trust=trust,
            claim=claim_obj,
            provenance=Provenance(
                source_type="conversation",
                source_id=source_conversation or "",
                recorded_by=self.user,
            ),
            anchors=list(anchors or []),
            applies=applies or "",
            when=when or {},
            op_id=op,
            expected_version=expected_version,
            draft_id=draft_id,
            supersedes=list(supersedes or []),
            force_authoritative=force_authoritative,
            is_spec=(prepared.layer == "spec"),
        )
        checked = gate.check(req, ctx)
        if not checked.ok:
            return fail(
                "; ".join(i.message for i in checked.errors()),
                checked.errors()[0].code if checked.errors() else "write_gate",
                issues=[i.__dict__ for i in checked.issues],
            )

        trust = checked.trust or trust
        response = RecordOps.record(
            self,
            module,
            entity,
            kind,
            content,
            supersedes=supersedes,
            anchors=anchors,
            draft_id=draft_id,
            source_conversation=source_conversation,
            aliases=aliases,
            status=checked.legacy_status,
            summary=summary,
            applies=applies,
            when=when,
            verify=verify,
            scope=scope,
            enforced_by=enforced_by,
        )
        if not response.get("ok"):
            return response

        mem_id = str(response.get("id") or response.get("draft_id") or "")
        versions = VersionStore(log)
        space_plain = to_plain(ctx.space)
        overlay = entry_meta_overlay(
            trust=trust,
            version=0,
            space=space_plain,
            claim=claim_obj,
            provenance=req.provenance,
        )
        overlay["content_sha256"] = content_hash(content)
        overlay["layer"] = prepared.layer
        overlay["profile_id"] = profile.id
        overlay["profile_kind"] = prepared.profile_kind
        snap = versions.commit(
            mem_id or new_ulid(),
            content,
            trust=trust,
            meta={"summary": summary or "", "module": module, "entity": entity, "kind": kind, **overlay},
            actor=self.user,
            space_key=ctx.space.isolation_key(),
            op_id=op,
            event_type="candidate_created" if trust.status == "candidate" else "updated",
            expected_version=expected_version,
        )
        overlay["version"] = snap.version

        entry = self.index.find(mem_id) if mem_id else None
        if entry is not None:
            entry.extra.update(overlay)
            path = self.storage.find_path(entry.id)
            if path:
                self.storage.rewrite(path, entry)
                self.index.refresh(force=True)

        all_issues = [i.__dict__ for i in prepared.issues] + [i.__dict__ for i in checked.issues]
        result = {
            **response,
            "umi": {
                "trust": to_plain(trust),
                "version": snap.version,
                "risk": checked.risk,
                "issues": all_issues,
                "op_id": op,
                "space": space_plain,
                "profile_id": profile.id,
                "layer": prepared.layer,
                "profile_kind": prepared.profile_kind,
            },
            "ok": True,
        }
        log.put_idempotent(op_key, snap.event_id, result)
        self._log("umi_record", conv=source_conversation, module=module, entity=entity,
                  trust=trust.status, version=snap.version, op_id=op, profile=profile.id)
        return result

    @returns_errors
    def promote_memory(
        self,
        memory_id: str,
        *,
        to_status: str = "validated",
        evidence: list[dict] | None = None,
        op_id: str | None = None,
        force_authoritative: bool = False,
    ) -> dict:
        rt = self.umi_runtime()
        record = rt.store.get(memory_id)
        if record is None:
            return fail(f"记忆不存在：{memory_id}", "not_found")
        ctx = self._ctx(module=record.module, entity=record.entity)
        ctx.assert_writable()
        if to_status not in ("validated", "authoritative"):
            return fail("只能晋升到 validated / authoritative", "trust_invalid")
        if to_status == "authoritative" and not force_authoritative:
            return fail("晋升权威知识需要 force_authoritative=true 与明确证据", "authority")

        trust = rt.trust.parse(record)
        try:
            for item in evidence or []:
                if isinstance(item, dict) and item.get("evidence_type"):
                    trust.evidence.append(
                        Evidence(
                            evidence_type=str(item["evidence_type"]),
                            source_id=str(item.get("source_id") or ""),
                            note=str(item.get("note") or ""),
                            verified=bool(item.get("verified", True)),
                        )
                    )
        except ValueError as exc:
            return fail(str(exc), "evidence")
        if not any(e.verified for e in trust.evidence):
            return fail("晋升需要至少一条已核实证据（evidence_type + verified）", "evidence")
        trust.status = to_status
        trust.verification = "verified"
        try:
            op = valid_op_id(op_id) or new_op_id("promote")
        except ValueError as exc:
            return fail(str(exc), "op_id")
        snap = rt.knowledge.commit(
            record.id,
            record.content,
            trust=trust,
            meta={"summary": record.summary, "module": record.module, **(record.extra or {})},
            actor=self.user,
            space_key=ctx.space.isolation_key(),
            op_id=op,
            event_type="promoted",
        )
        record.status = legacy_status_for_trust(to_status)
        record.trust = trust
        record.version = snap.version
        record.content_sha256 = content_hash(record.content)
        record.extra = {**(record.extra or {}), "trust": to_plain(trust), "version": snap.version,
                        "content_sha256": record.content_sha256}
        rt.store.save(record)
        return {"ok": True, "id": record.id, "trust": to_plain(trust), "version": snap.version}

    @returns_errors
    def rollback_memory(self, memory_id: str, to_version: int, *, op_id: str | None = None) -> dict:
        rt = self.umi_runtime()
        record = rt.store.get(memory_id)
        if record is None:
            return fail(f"记忆不存在：{memory_id}", "not_found")
        ctx = self._ctx(module=record.module, entity=record.entity)
        ctx.assert_writable()
        try:
            op = valid_op_id(op_id) or new_op_id("rollback")
        except ValueError as exc:
            return fail(str(exc), "op_id")
        snap = rt.knowledge.rollback(
            memory_id, to_version, actor=self.user, space_key=ctx.space.isolation_key(), op_id=op
        )
        record.content = snap.content
        record.extra = {**(record.extra or {}), **snap.meta, "version": snap.version}
        trust_meta = snap.meta.get("trust") if isinstance(snap.meta.get("trust"), dict) else None
        trust_status = (trust_meta or {}).get("status") or snap.trust_status
        if trust_status:
            record.status = legacy_status_for_trust(str(trust_status))
            if trust_meta is None:
                record.extra["trust"] = {
                    "status": trust_status,
                    "verification": "verified",
                }
            record.trust = parse_trust(record.extra, legacy_status=record.status)
        record.version = snap.version
        rt.store.save(record)
        return {"ok": True, "id": memory_id, "version": snap.version, "content": snap.content,
                "status": record.status}

    def governance_report(self) -> dict:
        rt = self.umi_runtime()
        profile = self.active_profile()
        data = rt.governance.report(
            rt.store.list(),
            spaces=self.spaces(),
            recovery_mode=is_recovery_mode(self.root),
            doctor_checks=profile.doctor_checks,
        )
        return {"ok": True, "profile_id": profile.id, **data}

    def set_recovery(self, enabled: bool) -> dict:
        path = set_recovery_mode(self.root, enabled, actor=self.user)
        return {"ok": True, "recovery_mode": enabled, "path": str(path)}

    def bootstrap_profile(self, profile_id: str | None = None) -> dict:
        from pmem.umi.profiles.bootstrap import ensure_all_core_profiles, ensure_profile_modules

        if profile_id:
            return ensure_profile_modules(self.root, profile_id)
        return ensure_all_core_profiles(self.root)

    def describe_profiles(self, profile_id: str | None = None) -> dict:
        from pmem.umi.profiles import all_profiles, list_profiles
        from pmem.umi.profiles.bootstrap import describe_profile

        if profile_id:
            return {"ok": True, "profile": describe_profile(profile_id)}
        return {
            "ok": True,
            "profiles": list_profiles(),
            "items": [p.as_dict() for p in all_profiles()],
            "active": self.active_profile().id,
        }

    def cross_space_link(
        self,
        *,
        mode: str,
        source_memory_id: str,
        source_profile: str,
        source_project: str,
        target_profile: str | None = None,
        authorized_by: str = "",
        note: str = "",
        agent_id: str = "human",
    ) -> dict:
        from pmem.umi.models import SpaceRef
        from pmem.umi.profiles.cross_space import CrossSpaceRequest, evaluate_cross_space, record_cross_space_event

        target_profile = target_profile or self.active_profile().id
        req = CrossSpaceRequest(
            mode=mode,
            source_memory_id=source_memory_id,
            source=SpaceRef(profile_id=source_profile, project_id=source_project),
            target=SpaceRef(profile_id=target_profile, project_id=self.spaces().project_id),
            authorized_by=authorized_by or self.user,
            note=note,
        )
        result = evaluate_cross_space(
            req,
            source_profile=get_profile(source_profile),
            target_profile=get_profile(target_profile),
            agent_id=agent_id,
        )
        if result.ok:
            record_cross_space_event(
                self.event_log(), result, actor=self.user, space_key=self.spaces().current().isolation_key()
            )
        return {
            "ok": result.ok,
            "mode": result.mode,
            "source_memory_id": result.source_memory_id,
            "target_hint": result.target_hint,
            "link": result.link,
            **({"error": result.error, "code": result.code} if not result.ok else {}),
        }
