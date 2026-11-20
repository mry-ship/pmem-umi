"""Trust & Evidence：来源、验证状态、可信等级、主张级证据。

原则：验证一条记忆，不代表其所有推论自动获得验证。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pmem.umi.models import (
    RECALLABLE_TRUST,
    REFERENCE_TRUST,
    TRUST_STATUSES,
    Evidence,
    KnowledgeClaim,
    Provenance,
    TrustInfo,
    trust_from_legacy_status,
)


@dataclass
class ClaimBundle:
    """一条记忆可含多个事实主张，各自追溯证据。"""

    claims: list[KnowledgeClaim] = field(default_factory=list)
    evidence_by_claim: dict[str, list[Evidence]] = field(default_factory=dict)

    def add(self, claim: KnowledgeClaim, evidence: list[Evidence] | None = None) -> None:
        self.claims.append(claim)
        if evidence:
            self.evidence_by_claim[claim.fingerprint()] = list(evidence)


def parse_trust(meta: dict[str, Any] | None, *, legacy_status: str = "active", verified: bool = False) -> TrustInfo:
    meta = meta or {}
    raw = meta.get("trust")
    if isinstance(raw, dict):
        status = str(raw.get("status") or "candidate")
        verification = str(raw.get("verification") or "unverified")
        evidence = []
        for item in raw.get("evidence") or []:
            if isinstance(item, dict) and item.get("evidence_type"):
                evidence.append(
                    Evidence(
                        evidence_type=str(item["evidence_type"]),
                        source_id=str(item.get("source_id") or ""),
                        note=str(item.get("note") or ""),
                        verified=bool(item.get("verified")),
                    )
                )
        return TrustInfo(
            status=status if status in TRUST_STATUSES else "candidate",
            verification=verification,
            evidence=evidence,
            confidence_note=str(raw.get("confidence_note") or ""),
        )
    if meta.get("trust_status"):
        status = str(meta["trust_status"])
        return TrustInfo(
            status=status if status in TRUST_STATUSES else "candidate",
            verification=str(meta.get("verification") or ("verified" if verified else "unverified")),
        )
    return trust_from_legacy_status(legacy_status, verified=verified)


def parse_provenance(meta: dict[str, Any] | None) -> Provenance:
    meta = meta or {}
    raw = meta.get("provenance")
    if isinstance(raw, dict):
        return Provenance(
            source_type=str(raw.get("source_type") or "conversation"),
            source_id=str(raw.get("source_id") or ""),
            extracted_by=str(raw.get("extracted_by") or ""),
            recorded_by=str(raw.get("recorded_by") or ""),
        )
    source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
    return Provenance(
        source_type="conversation",
        source_id=str(source.get("conversation") or ""),
        recorded_by=str(meta.get("author") or ""),
    )


def parse_claim(meta: dict[str, Any] | None) -> KnowledgeClaim | None:
    raw = (meta or {}).get("claim")
    if not isinstance(raw, dict):
        return None
    claim = KnowledgeClaim(
        subject=str(raw.get("subject") or ""),
        predicate=str(raw.get("predicate") or ""),
        object=str(raw.get("object") or ""),
    )
    return None if claim.is_empty() else claim


def trust_to_meta(trust: TrustInfo) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": trust.status,
        "verification": trust.verification,
    }
    if trust.confidence_note:
        data["confidence_note"] = trust.confidence_note
    if trust.evidence:
        data["evidence"] = [
            {
                "evidence_type": e.evidence_type,
                "source_id": e.source_id,
                "note": e.note,
                "verified": e.verified,
            }
            for e in trust.evidence
        ]
    return data


def can_auto_promote(trust: TrustInfo) -> bool:
    """低风险自动提升：仅用户明确确认等强证据。"""
    if trust.status not in ("candidate", "observation"):
        return False
    return any(e.evidence_type == "user_confirm" and e.verified for e in trust.evidence)


def promotion_risk(trust_status: str, *, is_spec: bool = False, is_decision: bool = False) -> str:
    """返回 L1 / L2 / L3 风险等级（系统规则，不交给模型判断）。"""
    if is_spec or trust_status == "authoritative" or is_decision:
        return "L3"
    if trust_status in ("validated", "superseded"):
        return "L2"
    return "L1"


def recall_disposition(trust: TrustInfo) -> str:
    """Safe Recall 处置：allow / reference / withhold。"""
    if trust.status == "rejected":
        return "withhold"
    if trust.status in RECALLABLE_TRUST and trust.verification in ("partial", "verified"):
        return "allow"
    if trust.status in REFERENCE_TRUST or trust.verification == "unverified":
        return "reference"
    return "withhold"


@dataclass
class ConflictItem:
    left_id: str
    right_id: str
    reason: str


def detect_claim_conflicts(
    existing: list[tuple[str, KnowledgeClaim | None, str]],
    incoming: KnowledgeClaim | None,
    *,
    incoming_kind: str = "",
) -> list[ConflictItem]:
    """简单冲突：同 subject+object 但 predicate 对立，或 correction/exclusion 对撞 conclusion。"""
    if incoming is None or incoming.is_empty():
        return []
    opposite = {
        ("associated_with", "not_associated_with"),
        ("causes", "not_causes"),
        ("requires", "forbids"),
        ("enabled", "disabled"),
    }
    conflicts: list[ConflictItem] = []
    for mem_id, claim, kind in existing:
        if claim is None or claim.is_empty():
            continue
        if claim.subject.lower() != incoming.subject.lower():
            continue
        if claim.object.lower() != incoming.object.lower():
            continue
        pair = (claim.predicate.lower(), incoming.predicate.lower())
        if pair in opposite or (pair[1], pair[0]) in opposite:
            conflicts.append(ConflictItem(mem_id, "incoming", f"主张冲突：{claim.predicate} vs {incoming.predicate}"))
        if incoming_kind == "correction" and kind == "conclusion" and claim.fingerprint() == incoming.fingerprint():
            conflicts.append(ConflictItem(mem_id, "incoming", "correction 针对同主张，需 supersedes"))
    return conflicts
