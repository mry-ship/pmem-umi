---
id: 01M7WQHHB0D3AS7JPNSBTYWJW1
module: feature.Tests
entity: UmiSuite
kind: feature
status: active
supersedes: []
anchors:
- tests/umi
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: UMI 测试覆盖 Profile 权限、入站隔离与既有闸门
applies: 跑 tests/umi 时
---
需求来源：核对无错漏。
必须保持：tests/umi 含 audit_candidates 跳过 archived；
无证据 promote 失败；
evidence 不能绕过 candidate_first；
safe_search 结果每条含 module；
cursor 写 Spec 被拒；
inbound personal→project=deny；
eval suite 全过。
入口：tests/umi/。
