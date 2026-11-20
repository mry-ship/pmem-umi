---
id: 01M7WQ0YZTP01B7X8A55C7NDNW
module: infra.Metrics
entity: UmiHealth
kind: risk
status: active
supersedes: []
anchors:
- src/pmem/metrics/health.py#_umi_health
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: Health/治理只报告，不得擅自改权威记忆
applies: 跑 pmem health 或 umi governance 时
---
看代码看不出的约束：治理 findings 再多也不能在 health 路径写回 entries；严重 critical 只提示 Recovery Mode。否则「巡检」本身会变成静默篡改权威知识的入口，与 UMI 原则冲突。
