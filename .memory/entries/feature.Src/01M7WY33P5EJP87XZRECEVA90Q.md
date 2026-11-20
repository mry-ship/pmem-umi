---
id: 01M7WY33P5EJP87XZRECEVA90Q
module: feature.Src
entity: Package
kind: feature
status: active
supersedes:
- 01M7WR2MMXQWFSTCGRJH6Q9QJ1
anchors:
- src/pmem/__init__.py
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: 对外安装与首页必须指向 mry-ship/pmem-umi（V0.1.0）
applies: 本仓库作为 Universal Memory Infrastructure 产品主体时
---
需求来源：用户要求更新 GitHub 首页与手册并打包发布。
必须保持：版本 0.1.0；
README/手册安装命令为 git+https://github.com/mry-ship/pmem-umi；
叙述为全新 UMI 产品而非旧 pmem 小版本；
手册含 UMI 三边界与 umi 命令。
入口：README.md、docs/pmem-guide.html、docs/umi-architecture.md、pyproject.toml。
