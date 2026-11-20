---
id: 01M7WTYE3AVF873Q0CG2TGT10F
module: infra.Umi
entity: SafeRecall
kind: conclusion
status: active
supersedes: []
anchors:
- src/pmem/umi/safe_recall.py
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 跨空间召回必须走 inbound_disposition 而非仅比 project_id
applies: 改 Safe Recall 过滤时
---
为什么：只比 project_id 时，同项目不同 Profile（如 personal 条目）仍可能 allow。
排除：跨空间一律 withhold（领域知识无法 reference）。
选法：inbound_disposition——personal 外泄 deny；
其它按目标 Profile inbound_default，检索侧最多 reference。
