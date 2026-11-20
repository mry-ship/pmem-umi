---
id: 01M7WRPJQTKX2EFNZVE44PGAA7
module: infra.Umi
entity: Profile
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/umi/profiles/engine.py
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: Profile 规则真正驱动写入权限、入站召回与治理检查集
applies: umi.enabled 时
---
需求来源：核对补全后的通用 Profile，发现声明未接通。
必须保持：prepare_write 对 layer=spec 校验 can_edit_spec；
Safe Recall 用 inbound_disposition（personal 外泄 deny，其它按 inbound_default 仅 reference）；
governance 按当前 Profile.doctor_checks 裁剪审计；
MCP controlled_record_memory 支持 profile_id/layer/agent_id 且 module 可空。
入口：profiles/engine.py、safe_recall.py、governance.py、server/app.py。
