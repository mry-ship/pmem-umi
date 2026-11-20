"""受控写入：七项检查 + Candidate 暂存 + 幂等事务。

AI 可提议修改；权威知识变更需验证/授权。宁可暂时不记，也不能污染长期记忆。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pmem.umi.models import (
    KnowledgeClaim,
    Provenance,
    TrustInfo,
    WriteOpId,
    content_hash,
    legacy_status_for_trust,
    valid_op_id,
)
from pmem.umi.space import IsolationError, SpaceContext, SpaceManager
from pmem.umi.trust import ConflictItem, detect_claim_conflicts, promotion_risk


@dataclass
class WriteRequest:
    module: str
    entity: str
    kind: str
    content: str
    summary: str = ""
    trust: TrustInfo = field(default_factory=lambda: TrustInfo(status="candidate"))
    claim: KnowledgeClaim | None = None
    provenance: Provenance = field(default_factory=Provenance)
    anchors: list[str] = field(default_factory=list)
    applies: str = ""
    when: dict = field(default_factory=dict)
    op_id: str | None = None
    expected_version: int | None = None
    draft_id: str | None = None
    supersedes: list[str] = field(default_factory=list)
    is_spec: bool = False
    force_authoritative: bool = False


@dataclass
class GateIssue:
    code: str
    message: str
    severity: str = "error"  # error / warn


@dataclass
class GateResult:
    ok: bool
    issues: list[GateIssue] = field(default_factory=list)
    trust: TrustInfo | None = None
    legacy_status: str = "seed"
    risk: str = "L1"
    op_key: str | None = None

    def errors(self) -> list[GateIssue]:
        return [i for i in self.issues if i.severity == "error"]


@dataclass
class WriteGate:
    spaces: SpaceManager
    existing_claims: Callable[[str], list[tuple[str, KnowledgeClaim | None, str]]] | None = None
    existing_summaries: Callable[[str], list[str]] | None = None

    def check(self, req: WriteRequest, ctx: SpaceContext) -> GateResult:
        issues: list[GateIssue] = []
        try:
            ctx.assert_writable()
        except IsolationError as exc:
            return GateResult(ok=False, issues=[GateIssue(exc.code, str(exc))])

        # 1. 归属检查
        if not req.module or not str(req.module).strip():
            issues.append(GateIssue("ownership", "缺少模块归属（module）"))
        if not req.entity or not str(req.entity).strip():
            issues.append(GateIssue("ownership", "缺少议题归属（entity）"))
        ctx.space.module_id = req.module
        ctx.space.entity_id = req.entity

        # 2. 重复检查（同模块 summary 近似）
        if self.existing_summaries and req.summary:
            known = self.existing_summaries(req.module)
            needle = req.summary.strip().lower()
            for s in known:
                if s.strip().lower() == needle:
                    issues.append(GateIssue("duplicate", f"同模块已有相同标题：{s}", "error"))
                    break

        # 3. 冲突检查
        if self.existing_claims and req.claim is not None:
            conflicts = detect_claim_conflicts(self.existing_claims(req.module), req.claim, incoming_kind=req.kind)
            for c in conflicts:
                if "需 supersedes" in c.reason and not req.supersedes:
                    issues.append(GateIssue("conflict", c.reason))
                elif "主张冲突" in c.reason:
                    issues.append(GateIssue("conflict", f"{c.reason}（与 {c.left_id}）"))

        # 4. 时间检查：正文暗示「曾经」但未写 applies/valid — 警告
        temporal_hints = ("以前", "曾经", "旧版", "当时", "historically", "used to")
        if any(h in (req.content or "") for h in temporal_hints) and not req.applies:
            issues.append(GateIssue("temporal", "疑似历史事实但未写 applies/适用条件", "warn"))

        # 5. 权威门槛：无授权先降级，再检查证据（避免「先报错再降级」）
        trust = req.trust
        risk = promotion_risk(trust.status, is_spec=req.is_spec, is_decision=req.kind == "decision")
        if trust.status == "authoritative" and not req.force_authoritative:
            issues.append(GateIssue("authority", "无明确授权：降级为 candidate 暂存", "warn"))
            trust = TrustInfo(
                status="candidate",
                verification="unverified",
                evidence=list(trust.evidence),
                confidence_note=trust.confidence_note or "awaiting authorization",
            )
            risk = "L1"
        if trust.status in ("validated", "authoritative") and trust.verification == "unverified":
            if not any(e.verified for e in trust.evidence):
                issues.append(
                    GateIssue("evidence", "已验证/权威等级需要至少一条已核实证据，或 verification≠unverified")
                )
        if trust.status == "authoritative" and not (
            req.force_authoritative
            or any(e.evidence_type in ("user_confirm", "spec", "code_verify", "test_result") and e.verified
                   for e in trust.evidence)
        ):
            issues.append(GateIssue("evidence", "权威知识需要用户确认 / Spec / 代码或测试证据"))

        # 6. 范围检查
        if req.kind in ("risk", "exclusion", "conclusion") and not req.applies and not req.when:
            issues.append(GateIssue("scope", "教训类记忆建议填写 applies 或 when", "warn"))

        # 7. 价值检查：过短或纯寒暄
        body = (req.content or "").strip()
        if len(body) < 20:
            issues.append(GateIssue("value", "内容过短，不值得进入长期记忆"))
        low_value = ("嗯", "好的", "谢谢", "ok", "thanks", "收到")
        if body.lower() in low_value or (len(body) < 40 and any(body.startswith(x) for x in low_value)):
            issues.append(GateIssue("value", "疑似一次性对话，不写入长期记忆"))

        # 默认不确定 → candidate
        if trust.status == "observation":
            trust = TrustInfo(status="candidate", verification="unverified", evidence=list(trust.evidence))

        op_id = None
        try:
            op_id = valid_op_id(req.op_id)
        except ValueError as exc:
            issues.append(GateIssue("op_id", str(exc)))

        op_key = None
        if op_id:
            op_key = WriteOpId(op_id=op_id, space=ctx.space, intent="record").key()

        errors = [i for i in issues if i.severity == "error"]
        return GateResult(
            ok=not errors,
            issues=issues,
            trust=trust,
            legacy_status=legacy_status_for_trust(trust.status),
            risk=risk,
            op_key=op_key,
        )


def fingerprint_request(req: WriteRequest) -> str:
    return content_hash(
        f"{req.module}|{req.entity}|{req.kind}|{req.summary}|{req.content}|{(req.claim.fingerprint() if req.claim else '')}"
    )
