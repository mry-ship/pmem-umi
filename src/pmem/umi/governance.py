"""Quality & Governance：Doctor / Health / Report 扩展（隔离、漂移、证据、冲突）。

Doctor 发现问题不擅自修复权威知识；严重完整性问题可进入 Recovery Mode。
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pmem.umi.events import EventLog, event_log_path
from pmem.umi.models import content_hash
from pmem.umi.space import SpaceManager
from pmem.umi.trust import parse_claim, parse_trust


@dataclass
class GovernanceFinding:
    area: str
    severity: str  # info / warn / critical
    message: str
    memory_id: str | None = None


@dataclass
class GovernanceReport:
    findings: list[GovernanceFinding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recovery_recommended: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [
                {
                    "area": f.area,
                    "severity": f.severity,
                    "message": f.message,
                    **({"memory_id": f.memory_id} if f.memory_id else {}),
                }
                for f in self.findings
            ],
            "metrics": self.metrics,
            "recovery_recommended": self.recovery_recommended,
        }


def _entry_trust_and_space(entry) -> tuple[Any, dict]:
    extra = getattr(entry, "extra", {}) or {}
    trust = parse_trust(extra, legacy_status=entry.status, verified=bool(entry.verified))
    space = extra.get("space") if isinstance(extra.get("space"), dict) else {}
    return trust, space


def audit_isolation(entries: list[Any], spaces: SpaceManager) -> list[GovernanceFinding]:
    findings = []
    for entry in entries:
        _, space = _entry_trust_and_space(entry)
        pid = space.get("project_id")
        if pid and pid != spaces.project_id:
            findings.append(
                GovernanceFinding(
                    "Isolation Health",
                    "critical",
                    f"记忆 {entry.id} 标注项目 {pid}，与当前 {spaces.project_id} 不一致",
                    entry.id,
                )
            )
    return findings


def audit_integrity(entries: list[Any], log: EventLog | None) -> list[GovernanceFinding]:
    findings = []
    if log is not None:
        for problem in log.verify_integrity():
            findings.append(GovernanceFinding("Knowledge Integrity", "critical", problem))
    for entry in entries:
        extra = getattr(entry, "extra", {}) or {}
        expected = extra.get("content_sha256")
        if expected:
            actual = content_hash(entry.content)
            if actual != expected:
                findings.append(
                    GovernanceFinding(
                        "Knowledge Integrity",
                        "critical",
                        f"正文 hash 不匹配（可能被意外修改）",
                        entry.id,
                    )
                )
        if not extra.get("provenance") and not entry.source_conversation and not entry.author:
            findings.append(
                GovernanceFinding(
                    "Knowledge Integrity",
                    "warn",
                    "缺少来源追溯（provenance / author）",
                    entry.id,
                )
            )
    return findings


def audit_conflicts(entries: list[Any]) -> list[GovernanceFinding]:
    from pmem.umi.trust import detect_claim_conflicts

    findings = []
    by_module: dict[str, list] = {}
    for entry in entries:
        if entry.status == "archived":
            continue
        claim = parse_claim(getattr(entry, "extra", {}) or {})
        by_module.setdefault(entry.module, []).append((entry.id, claim, entry.kind))
    for module, rows in by_module.items():
        for i, (mid, claim, kind) in enumerate(rows):
            others = rows[:i] + rows[i + 1 :]
            for c in detect_claim_conflicts(others, claim, incoming_kind=kind):
                findings.append(
                    GovernanceFinding(
                        "Conflict Health",
                        "warn",
                        f"{module}: {c.reason}（{c.left_id}）",
                        mid,
                    )
                )
    return findings


def audit_drift(log: EventLog | None, *, sample: int = 50) -> list[GovernanceFinding]:
    """对比版本内容 hash：多次变更后若 summary/主张指纹剧变则标疑似漂移。"""
    findings = []
    if log is None:
        return findings
    seen = 0
    for event in log.iter_events(limit=200):
        if event.event_type not in ("merged", "updated", "promoted") or not event.memory_id:
            continue
        versions = []
        latest = log.latest_version(event.memory_id)
        if latest < 2:
            continue
        for v in range(max(1, latest - 2), latest + 1):
            row = log.get_version(event.memory_id, v)
            if row:
                versions.append(row)
        if len(versions) < 2:
            continue
        older, newer = versions[0], versions[-1]
        if older["content_hash"] != newer["content_hash"]:
            # 粗检：长度变化超过 50% 且事件为 merge
            o_len, n_len = len(older["content"]), len(newer["content"])
            if event.event_type == "merged" and o_len > 0 and abs(n_len - o_len) / o_len > 0.5:
                findings.append(
                    GovernanceFinding(
                        "Drift Health",
                        "warn",
                        f"合并后正文长度变化超过 50%，请人工核对是否混入无关因果",
                        event.memory_id,
                    )
                )
        seen += 1
        if seen >= sample:
            break
    return findings


def audit_candidates(entries: list[Any]) -> list[GovernanceFinding]:
    findings = []
    n = 0
    for entry in entries:
        if getattr(entry, "status", None) == "archived":
            continue
        trust, _ = _entry_trust_and_space(entry)
        if trust.status == "candidate" or entry.status in ("seed", "draft"):
            n += 1
    if n:
        findings.append(
            GovernanceFinding("Evolution Health", "info", f"待处理候选记忆 {n} 条")
        )
    return findings


def audit_temporal(entries: list[Any]) -> list[GovernanceFinding]:
    findings = []
    for entry in entries:
        trust, _ = _entry_trust_and_space(entry)
        if trust.status == "superseded" and entry.status == "active":
            findings.append(
                GovernanceFinding(
                    "Temporal Health",
                    "warn",
                    "trust=superseded 但仍为 active，可能过期知识冒充当前",
                    entry.id,
                )
            )
    return findings


def run_governance(
    root: Path,
    entries: list[Any],
    *,
    spaces: SpaceManager | None = None,
    recovery_mode: bool = False,
    doctor_checks: tuple[str, ...] | list[str] | None = None,
) -> GovernanceReport:
    root = Path(root)
    spaces = spaces or SpaceManager.from_config(root, _LazyConfig(root))
    log_path = event_log_path(root)
    log = EventLog(log_path) if log_path.exists() else None
    # 未指定时跑全套；指定则按 Profile.doctor_checks 裁剪（未知名忽略）
    if doctor_checks is None:
        try:
            from pmem.umi.profiles.engine import current_profile

            doctor_checks = current_profile(_LazyConfig(root)).doctor_checks
        except Exception:  # noqa: BLE001
            doctor_checks = ("isolation", "integrity", "conflicts", "drift", "candidates", "temporal")
    enabled = {str(c).strip().lower() for c in doctor_checks if str(c).strip()}
    # spec/evidence 等声明型检查暂无独立审计器，映射到邻近检查或跳过
    findings: list[GovernanceFinding] = []
    if "isolation" in enabled:
        findings.extend(audit_isolation(entries, spaces))
    if "integrity" in enabled:
        findings.extend(audit_integrity(entries, log))
    if "conflicts" in enabled:
        findings.extend(audit_conflicts(entries))
    if "drift" in enabled:
        findings.extend(audit_drift(log))
    if "candidates" in enabled:
        findings.extend(audit_candidates(entries))
    if "temporal" in enabled:
        findings.extend(audit_temporal(entries))
    if recovery_mode:
        findings.append(
            GovernanceFinding("Recovery", "critical", "当前处于 Read-only Recovery Mode")
        )
    critical = sum(1 for f in findings if f.severity == "critical")
    metrics = {
        "entries": len(entries),
        "findings": len(findings),
        "critical": critical,
        "by_area": dict(Counter(f.area for f in findings)),
        "doctor_checks": sorted(enabled),
    }
    if log is not None:
        log.close()
    return GovernanceReport(
        findings=findings,
        metrics=metrics,
        recovery_recommended=critical > 0,
    )


class _LazyConfig:
    """无完整 Config 时的最小适配。"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._data = {}
        cfg = self.root / ".memory" / "config.yaml"
        if cfg.exists():
            import yaml

            self._data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}

    def get(self, key, default=None):
        if key == "umi":
            return self._data.get("umi") or {}
        if key == "project":
            return self._data.get("project") or {}
        cur: Any = self._data
        for part in str(key).split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def false_recall_rate(adopted: list[dict[str, Any]]) -> dict[str, float]:
    """错误召回率及相关拆分。adopted 项需含 flags: inapplicable/stale/wrong_link/ok。"""
    total = len(adopted) or 1
    bad = [a for a in adopted if a.get("flag") in ("inapplicable", "stale", "wrong_link", "error")]
    by = Counter(a.get("flag") for a in bad)
    return {
        "false_recall_rate": len(bad) / total,
        "inapplicable_rate": by.get("inapplicable", 0) / total,
        "stale_rate": by.get("stale", 0) / total,
        "wrong_link_rate": by.get("wrong_link", 0) / total,
        "sample_size": len(adopted),
    }


def set_recovery_mode(root: Path, enabled: bool, *, actor: str = "system") -> Path:
    path = Path(root) / ".memory" / "umi" / "recovery.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"enabled": bool(enabled), "updated_by": actor}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log = EventLog(event_log_path(root))
    log.append(
        "recovery_enter" if enabled else "recovery_exit",
        data,
        actor=actor,
        space_key=str(root),
    )
    log.close()
    return path


def is_recovery_mode(root: Path) -> bool:
    path = Path(root) / ".memory" / "umi" / "recovery.json"
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("enabled"))
    except (OSError, json.JSONDecodeError):
        return False
