"""UMI 统一数据协议：信任等级、证据、空间、主张、写入操作 ID。

与现有 Entry（Markdown）并存：权威正文仍落在 .memory/entries；
事件、版本、候选暂存、审计进 SQLite（可重建索引，不可当作唯一知识源）。
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Observation 只进事件日志；候选及以后可物质化为 Entry
TRUST_STATUSES = (
    "observation",
    "candidate",
    "validated",
    "authoritative",
    "rejected",
    "superseded",
    "archived",
)
# 默认可进入 Safe Recall 的等级（权威与已验证）
RECALLABLE_TRUST = frozenset({"validated", "authoritative"})
# 可作为「参考」返回（需标记），不可当当前结论
REFERENCE_TRUST = frozenset({"candidate", "superseded"})

EVIDENCE_TYPES = (
    "user_confirm",
    "code_verify",
    "test_result",
    "external_doc",
    "conversation",
    "inference",
    "spec",
)

PROFILES = ("personal", "project", "team", "domain")

_OP_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def new_op_id(prefix: str = "op") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def valid_op_id(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not _OP_ID_RE.match(text):
        raise ValueError(f"op_id 格式无效：{text!r}")
    return text


@dataclass
class SpaceRef:
    profile_id: str = "project"
    owner_id: str = ""
    project_id: str = ""
    module_id: str = ""
    entity_id: str = ""

    def isolation_key(self) -> str:
        return "|".join(
            [
                self.profile_id or "project",
                self.owner_id or "",
                self.project_id or "",
                self.module_id or "",
            ]
        )


@dataclass
class KnowledgeClaim:
    subject: str = ""
    predicate: str = ""
    object: str = ""

    def is_empty(self) -> bool:
        return not (self.subject or self.predicate or self.object)

    def fingerprint(self) -> str:
        raw = f"{self.subject.strip().lower()}|{self.predicate.strip().lower()}|{self.object.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class Evidence:
    evidence_type: str
    source_id: str = ""
    note: str = ""
    verified: bool = False

    def __post_init__(self) -> None:
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"evidence_type 必须是 {' / '.join(EVIDENCE_TYPES)} 之一")


@dataclass
class Provenance:
    source_type: str = "conversation"
    source_id: str = ""
    extracted_by: str = ""
    recorded_by: str = ""


@dataclass
class TrustInfo:
    status: str = "candidate"
    # 不用模型随意打分当概率；存证据类型与验证状态，confidence 仅作辅助展示
    verification: str = "unverified"  # unverified / partial / verified / rejected
    evidence: list[Evidence] = field(default_factory=list)
    confidence_note: str = ""

    def __post_init__(self) -> None:
        if self.status not in TRUST_STATUSES:
            raise ValueError(f"trust.status 必须是 {' / '.join(TRUST_STATUSES)} 之一")

    @property
    def recallable(self) -> bool:
        return self.status in RECALLABLE_TRUST and self.verification in ("partial", "verified")


@dataclass
class WriteOpId:
    """幂等写入键：同一 op_id 重复执行返回已有结果。"""

    op_id: str
    space: SpaceRef
    intent: str = "record"  # record / promote / merge / archive / rollback

    def key(self) -> str:
        return f"{self.intent}:{self.op_id}:{self.space.isolation_key()}"


def trust_from_legacy_status(status: str, *, verified: bool = False) -> TrustInfo:
    """旧记忆兼容映射。"""
    if status == "archived":
        return TrustInfo(status="archived", verification="verified" if verified else "unverified")
    if status in ("draft", "seed"):
        return TrustInfo(status="candidate", verification="unverified")
    if verified:
        return TrustInfo(status="validated", verification="verified")
    return TrustInfo(status="validated", verification="partial")


def legacy_status_for_trust(trust_status: str) -> str:
    """写入 Entry.status 时的映射：保持闸门 / 检索可见性兼容。"""
    if trust_status in ("observation", "candidate"):
        return "seed"
    if trust_status == "rejected":
        return "archived"
    if trust_status in ("superseded", "archived"):
        return "archived"
    return "active"


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def to_plain(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
