---
id: 01M7WXY3PA7WKAYT5G2XBRPX66
module: infra.Umi
entity: CorePorts
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/umi/core/ports.py
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: UMI 业务必须只依赖 Core 端口，换底层只换 Adapter
applies: umi.enabled 时
---
需求来源：用户要求划清三边界，并建立稳定接口以免未来剥离时大迁移。
必须保持：MemoryStore/MemoryRetriever/KnowledgeRepository/TrustManager/SpaceManagerPort/GovernanceEngine 定义在 umi.core；
pmem 实现仅在 umi.adapters.pmem；
Safe Recall / promote / rollback / governance 经 UmiRuntime 使用端口；
MemoryRecord 不依赖 Entry。
入口：umi/core/、adapters/pmem.py、service.umi_ops.umi_runtime。
