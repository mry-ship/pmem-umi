---
id: 01M7WT2CXXH3R523AGCZFTZB5F
module: feature.Src
entity: Package
kind: feature
status: active
supersedes:
- 01M7WSTWWJ4WMJT9SG4NNR7A82
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 包版本必须标识为全新产品 V0.1.0
applies: 本仓库作为 Universal Memory Infrastructure 产品主体时
---
需求来源：用户明确纠正——本项目不是上游 pmem 的后续版本，而是全新产品线，版本号为 V0.1.0。
循环检查曾误改回 0.8.0，已纠正。
必须保持：pmem.__version__ 与 pyproject 均为 0.1.0；
对外叙述不得写成 0.8/pmem 小版本升级。
入口：src/pmem/__init__.py、pyproject.toml、README、docs/umi-architecture.md。
