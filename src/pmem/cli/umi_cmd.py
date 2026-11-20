"""pmem umi：Universal Memory Infrastructure 命令。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def run_umi(args) -> int:
    from pmem.service import MemoryService
    from pmem.umi.eval import run_eval_suite

    root = Path(args.root).resolve()
    action = args.umi_action
    if action == "eval":
        suite = run_eval_suite()
        print(json.dumps(suite.as_dict(), ensure_ascii=False, indent=2))
        return 0 if suite.ok else 1

    svc = MemoryService(root)
    try:
        if action == "profiles":
            data = svc.describe_profiles(getattr(args, "id", None) or None)
            if not getattr(args, "full", False) and not getattr(args, "id", None):
                data = {
                    "ok": True,
                    "profiles": data.get("profiles"),
                    "active": data.get("active"),
                }
        elif action == "bootstrap":
            data = svc.bootstrap_profile(getattr(args, "profile", None) or None)
        elif action == "cross":
            data = svc.cross_space_link(
                mode=args.mode,
                source_memory_id=args.source_id,
                source_profile=args.source_profile,
                source_project=args.source_project,
                target_profile=getattr(args, "target_profile", None) or None,
                authorized_by=getattr(args, "authorized_by", "") or "",
                note=getattr(args, "note", "") or "",
                agent_id=getattr(args, "agent", None) or "human",
            )
        elif action == "governance":
            data = svc.governance_report()
        elif action == "recovery":
            data = svc.set_recovery(bool(args.enable))
        elif action == "promote":
            evidence = []
            if getattr(args, "evidence", None):
                evidence.append(
                    {
                        "evidence_type": args.evidence,
                        "note": args.note or "",
                        "verified": True,
                    }
                )
            data = svc.promote_memory(
                args.id,
                to_status=args.to,
                evidence=evidence or None,
                force_authoritative=bool(args.force),
            )
        elif action == "rollback":
            data = svc.rollback_memory(args.id, args.version)
        elif action == "record":
            claim = None
            if args.subject or args.predicate or args.object:
                claim = {
                    "subject": args.subject or "",
                    "predicate": args.predicate or "",
                    "object": args.object or "",
                }
            content = args.content
            if content == "-":
                content = sys.stdin.read()
            data = svc.controlled_record(
                getattr(args, "module", "") or "",
                args.entity,
                args.kind,
                content,
                summary=args.summary or None,
                trust_status=args.trust,
                verification=args.verification,
                claim=claim,
                op_id=args.op_id or None,
                force_authoritative=bool(args.force),
                promote=bool(args.promote),
                layer=getattr(args, "layer", None) or "memory",
                agent_id=getattr(args, "agent", None) or "default",
                profile_id=getattr(args, "profile", None) or None,
            )
        elif action == "search":
            data = svc.safe_search(
                module=args.module or None,
                path=args.path or None,
                entity=args.entity or None,
                query=args.query or None,
                limit=args.limit,
            )
        else:
            print(f"未知 umi 动作：{action}", file=sys.stderr)
            return 2
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get("ok", True) else 1
    finally:
        svc.close()
