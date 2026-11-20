---
id: 01M7WXY4VDRM34BKZ9VFTVCY4E
module: infra.Umi
entity: CorePorts
kind: decision
status: active
supersedes: []
anchors: []
revision: git:63d9047
author: 1002378395@qq.com
note_date: '2026-11-21'
summary: pmem 是 UMI 技术起点，不是永远依赖；先复用再解耦
applies: 规划 UMI 与 pmem 关系时
---
为什么：立刻重写存储会丢真实验证过的检索/闸门；
永久绑 Entry 则无法独立演进。
排除：让 UMI 业务直接 import Entry/Index；
或现在就拆成两仓重写。选法：
  ① Adapter 复用 pmem；
  ② UMI 专注隔离信任治理；
  ③ 日后换 Adapter 解耦。
三边界：Core=存储检索事件版本权限；
pmem=模块映射 Spec 拦截；
Profile=策略。
