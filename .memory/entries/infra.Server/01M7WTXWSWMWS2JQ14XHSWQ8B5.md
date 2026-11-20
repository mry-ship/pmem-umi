---
id: 01M7WTXWSWMWS2JQ14XHSWQ8B5
module: infra.Server
entity: McpUmi
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/server/app.py#controlled_record_memory
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: MCP controlled_record 必须暴露 Profile/layer/agent
applies: 通过 MCP 写入 UMI 时
---
需求来源：核对发现 CLI 已支持但 MCP 未传。
必须保持：controlled_record_memory 接受 module 可空、layer、profile_id、agent_id，并下传到 UmiOps.controlled_record。
入口：src/pmem/server/app.py。
