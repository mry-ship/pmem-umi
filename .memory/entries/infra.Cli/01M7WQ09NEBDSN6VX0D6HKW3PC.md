---
id: 01M7WQ09NEBDSN6VX0D6HKW3PC
module: infra.Cli
entity: UmiCmd
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/cli/umi_cmd.py
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: umi 子命令必须覆盖受控写入、召回、晋升、回滚、治理与评测
applies: 命令行运维与 Agent 终端兜底时
---
需求来源：用户要求把隔离/信任/版本/Safe Recall/治理落到可执行入口。
必须保持：pmem umi record|search|promote|rollback|governance|recovery|eval|profiles 可用；
doctor 输出 UMI 启用状态与治理 critical 摘要；
eval/profiles 可不依赖完整项目根。
入口：src/pmem/cli/main.py（umi 解析）、src/pmem/cli/umi_cmd.py、doctor_cmd 的 UMI 段。
