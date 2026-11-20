---
id: 01M7WRPRGR9559QXAGDSK4KES9
module: infra.Umi
entity: Profile
kind: decision
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 通用底座靠 Profile 规则，不靠改引擎加行业
applies: 扩展新场景时
---
为什么：若每来一个行业就改 Core，通用引擎会迅速腐化。
排除：把 Personal/Team 逻辑写死进 record/search。
选法：Profile 声明 kinds/lifecycle/doctor/cross_space/agent 权限，extensions 只注册，引擎只执行。
