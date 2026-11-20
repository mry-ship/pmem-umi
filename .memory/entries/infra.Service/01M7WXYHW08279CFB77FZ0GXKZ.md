---
id: 01M7WXYHW08279CFB77FZ0GXKZ
module: infra.Service
entity: UmiOps
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/service/umi_ops.py#umi_runtime
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: UmiOps 经 umi_runtime 访问 Core 端口，不直接绑 Index/Entry
applies: umi.enabled 时调用 promote/rollback/safe_search/governance
---
需求来源：用户要求端口化以便日后解耦。
必须保持：umi_runtime() 装配 PmemAdapter；
safe_search/promote_memory/rollback_memory/governance_report 走 Store/Retriever/Knowledge/Trust/Governance 端口。
候选首写仍可经 RecordOps（pmem 质量闸门），属复用阶段。
入口：MemoryService.umi_runtime。
