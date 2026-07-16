# 老师小助手

海外教学知识库治理体系 + 钉钉 Agent 问答入口测试版。

## 当前能力

- 老师可在钉钉群内 @海外教学小助手 提问。
- 已有知识可按“结论、流程、材料、提醒”结构回答。
- 板块内容为“无”时自动隐藏。
- 敏感问题自动拦截。
- 未命中问题进入治理群补充审核。
- 已答复但有问题的答案可走纠错更新链路。
- 审核通过后自动写入分级知识库。
- 支持交互明细和月度统计报表导出。

## 知识分级

- 公开可答知识：普通老师可获得答案。
- 职能白名单知识：后续仅对白名单角色开放。
- 敏感暂不回答知识：只做治理归档，不直接回答老师。

## 治理链路

- 未命中补充：老师群简短提示，治理群补正文并审核入库。
- 答案纠错：老师群简短提示，治理群更新正文并审核更新。
- 审核分级：公开 / 白名单 / 敏感。
- 治理通知：通过固定自定义机器人 Webhook 推送到治理群。

## 主要文档

- [知识库治理规则](./GOVERNANCE.md)
- [知识库未命中与纠错流转](./FLOWS.md)

## 数据文件

- `data/analytics_events.jsonl`：提问和答复记录。
- `data/pending_questions.jsonl`：未命中待补充记录。
- `data/correction_reports.jsonl`：纠错记录。
- `data/draft_answers.jsonl`：补充正文记录。
- `data/correction_drafts.jsonl`：更新正文记录。
- `data/governance_actions.jsonl`：审核动作记录。
- `data/teacher_directory.json`：老师身份和组织映射。
- `data/owner_routes.json`：负责人路由配置。
- `data/governance_channel.json`：治理群推送配置。

## 报表生成

```bash
python monthly_report.py 2026-06
```

生成结果在 `data/reports/`。

## 维护原则

- 有正文，才有答案。
- 答案直接给，不让老师自己找文档。
- 没有确认正文的问题不编造。
- 敏感内容宁可不答，也不要越权答。
