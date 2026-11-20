---
id: 01M7WXY5FB4KYMYPNCXYG62PFQ
module: infra.Umi
entity: CorePorts
kind: exclusion
status: active
supersedes: []
anchors:
- src/pmem/umi/core/ports.py
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: 禁止 UMI 业务层直接依赖 pmem.Entry 内部结构
applies: 改 Safe Recall / 治理 / 晋升时
---
试过不行：业务直接读 Entry.extra/status 会把 Markdown 记忆模型焊进通用层。
排除：在 safe_recall/governance 里 import Entry。
选法：只认 MemoryRecord；
Entry↔Record 转换仅允许出现在 adapters/pmem.py。
