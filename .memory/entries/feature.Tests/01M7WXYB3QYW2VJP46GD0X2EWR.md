---
id: 01M7WXYB3QYW2VJP46GD0X2EWR
module: feature.Tests
entity: UmiSuite
kind: feature
status: active
supersedes:
- 01M7WQHHB0D3AS7JPNSBTYWJW1
anchors:
- tests/umi
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: UMI 测试覆盖端口协议、Profile 权限与既有闸门
applies: 跑 tests/umi 时
---
需求来源：Core 端口落地。
必须保持：tests/umi 含端口 isinstance 与 promote 经 Runtime；
audit_candidates 跳过 archived；
无证据 promote 失败；
safe_search 含 module；
cursor 写 Spec 被拒；
inbound personal→project=deny；
eval suite 全过。
入口：tests/umi/。
