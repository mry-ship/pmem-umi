---
id: 01M7WQ0ADPRX3WGE3HH0PGJVHQ
module: infra.Metrics
entity: UmiHealth
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/metrics/health.py#_umi_health
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: health 报告必须包含 UMI 治理发现与 Recovery 提示
applies: umi.enabled 时跑 pmem health
---
需求来源：用户要求 Doctor/Health/Report 成为自我保护机制，不能只统计命中率。
必须保持：build_health 含 umi 节（隔离/完整性/冲突/漂移等 findings）；
render 列出 critical 并在 recovery 时加重提示；
不在 health 里擅自修复权威知识。
入口：src/pmem/metrics/health.py。
