---
id: 01M7WSTWWJ4WMJT9SG4NNR7A82
module: feature.Src
entity: Package
kind: feature
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 包版本对齐 0.8.0（UMI）
---
需求来源：循环检查发现 __init__/pyproject/测试版本不一致。
必须保持：src/pmem/__init__.py 与 pyproject.toml 均为 0.8.0；
tests 断言 0.8.0。
入口：src/pmem/__init__.py。
