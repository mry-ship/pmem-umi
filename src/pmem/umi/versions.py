"""Versioned Knowledge：当前知识可更新，每次变化保留版本；支持回滚。

原始记录保留在 Event Log；权威 Markdown 是当前物化视图之一。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pmem.umi.events import EventLog
from pmem.umi.models import TrustInfo, content_hash, to_plain, utc_now_iso
from pmem.umi.trust import trust_to_meta


@dataclass
class VersionSnapshot:
    memory_id: str
    version: int
    trust_status: str
    content: str
    content_hash: str
    meta: dict[str, Any]
    event_id: str
    created_at: str


class VersionStore:
    def __init__(self, log: EventLog):
        self.log = log

    def next_version(self, memory_id: str) -> int:
        return self.log.latest_version(memory_id) + 1

    def commit(
        self,
        memory_id: str,
        content: str,
        *,
        trust: TrustInfo,
        meta: dict[str, Any],
        actor: str,
        space_key: str,
        op_id: str | None = None,
        event_type: str = "updated",
        expected_version: int | None = None,
    ) -> VersionSnapshot:
        current = self.log.latest_version(memory_id)
        if expected_version is not None and current != expected_version:
            raise ConcurrentModification(
                f"版本冲突：期望 {expected_version}，实际 {current}；请重新合并后再写"
            )
        version = current + 1
        payload = {
            "memory_id": memory_id,
            "version": version,
            "trust": trust_to_meta(trust),
            "meta": meta,
            "content_hash": content_hash(content),
        }
        event = self.log.append(
            event_type,
            payload,
            op_id=op_id,
            space_key=space_key,
            memory_id=memory_id,
            actor=actor,
        )
        full_meta = {**meta, "trust": trust_to_meta(trust), "version": version, "updated_at": utc_now_iso()}
        self.log.save_version(
            memory_id,
            version,
            trust_status=trust.status,
            content=content,
            meta=full_meta,
            event_id=event.event_id,
        )
        return VersionSnapshot(
            memory_id=memory_id,
            version=version,
            trust_status=trust.status,
            content=content,
            content_hash=content_hash(content),
            meta=full_meta,
            event_id=event.event_id,
            created_at=event.created_at,
        )

    def get(self, memory_id: str, version: int | None = None) -> VersionSnapshot | None:
        ver = version if version is not None else self.log.latest_version(memory_id)
        if ver <= 0:
            return None
        row = self.log.get_version(memory_id, ver)
        if not row:
            return None
        import json

        return VersionSnapshot(
            memory_id=memory_id,
            version=int(row["version"]),
            trust_status=row["trust_status"],
            content=row["content"],
            content_hash=row["content_hash"],
            meta=json.loads(row["meta_json"]),
            event_id=row["event_id"],
            created_at=row["created_at"],
        )

    def rollback(
        self,
        memory_id: str,
        to_version: int,
        *,
        actor: str,
        space_key: str,
        op_id: str | None = None,
    ) -> VersionSnapshot:
        snap = self.get(memory_id, to_version)
        if snap is None:
            raise LookupError(f"找不到 {memory_id} 的版本 {to_version}")
        # 保留快照原 verification，避免回滚到 candidate 却被标成 verified
        prev_verification = "unverified"
        raw_trust = snap.meta.get("trust") if isinstance(snap.meta.get("trust"), dict) else None
        if raw_trust and raw_trust.get("verification"):
            prev_verification = str(raw_trust["verification"])
        trust = TrustInfo(status=snap.trust_status, verification=prev_verification)
        meta = {**snap.meta, "rolled_back_to": to_version}
        if raw_trust is not None:
            meta["trust"] = {**raw_trust, "status": snap.trust_status, "verification": prev_verification}
        return self.commit(
            memory_id,
            snap.content,
            trust=trust,
            meta=meta,
            actor=actor,
            space_key=space_key,
            op_id=op_id,
            event_type="rolled_back",
        )


class ConcurrentModification(RuntimeError):
    pass


def entry_meta_overlay(
    *,
    trust: TrustInfo,
    version: int,
    space: dict[str, Any] | None = None,
    claim: Any = None,
    provenance: Any = None,
) -> dict[str, Any]:
    """写入 Entry.extra / YAML 的 UMI 字段。"""
    overlay: dict[str, Any] = {
        "trust": trust_to_meta(trust),
        "version": version,
        "content_sha256": None,  # 由调用方填
    }
    if space:
        overlay["space"] = space
    if claim is not None and hasattr(claim, "is_empty") and not claim.is_empty():
        overlay["claim"] = to_plain(claim)
    if provenance is not None:
        overlay["provenance"] = to_plain(provenance)
    return overlay
