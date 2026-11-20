---
id: 01M7WTZHFT040G2CGRC5FECRDX
module: infra.Server
entity: McpUmi
kind: exclusion
status: active
supersedes: []
anchors:
- src/pmem/server/app.py#controlled_record_memory
revision: none
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: 不能假设 CLI 已有的 UMI 参数会自动出现在 MCP
applies: 给 umi_ops 加 CLI 参数后同步 MCP 时
---
试过不行：只改 CLI/UmiOps，以为 MCP controlled_record_memory 会跟着暴露 profile/layer/agent。
实际 MCP 工具签名是手写白名单，漏传则 Agent 经 MCP 写 personal/team 时 module 必填、无法选 Profile。
排除：只测 CLI 就当接入完成。
必须同步改 server/app.py 工具参数并下传到 controlled_record。
