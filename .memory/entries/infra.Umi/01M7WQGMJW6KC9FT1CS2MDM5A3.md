---
id: 01M7WQGMJW6KC9FT1CS2MDM5A3
module: infra.Umi
entity: Governance
kind: exclusion
status: active
supersedes: []
anchors:
- src/pmem/umi/governance.py#audit_candidates
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 候选审计必须跳过已归档记忆
applies: 跑 umi governance / doctor UMI 段时
---
试过不行：audit_candidates 把 status=archived 但仍带 trust=candidate 的探针也算进待处理候选，归档后治理仍报 4 条候选积压，造成误报。
排除：对 index.entries() 全量计数。
正确：候选/种子审计跳过 archived。
