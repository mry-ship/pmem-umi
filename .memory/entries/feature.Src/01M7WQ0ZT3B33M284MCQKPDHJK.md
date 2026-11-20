---
id: 01M7WQ0ZT3B33M284MCQKPDHJK
module: feature.Src
entity: Package
kind: decision
status: active
supersedes: []
anchors:
- .memory/modules.yaml
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: Src 粗模块必须拆成 infra.*，禁止再 paths=src/**
applies: 本仓库模块划分
---
为什么：自动 sync 曾把整个 src/** 登记为 feature.Src，闸门与记忆归属过粗，UMI/Cli/Service 改动会串到同一模块。
排除：继续用一个 Src 兜底。
选法：src/pmem 按职责拆 infra.Umi/Core/Service/Cli/Metrics 等；
feature.Src 仅保留 __init__.py 作版本入口追溯。
