# 长篇网文写作 Agent 设计文档

## 目标

创建一套面向 100 万到 300 万字网文项目的多 Agent 写作体系。体系支持连续写作、续写、改写、扩写、节奏调整，并通过 Markdown 文件保存项目资料。

## 范围

包含：
- 多 Agent 团队设计
- 工作流程
- 项目模板
- 合规名称规则
- 章节审稿标准

不包含：
- 具体小说正文
- 特定平台发布功能
- 自动联网检索

## 架构

系统由总主编剧 Agent 统一调度，其余 Agent 负责类型规则、世界观、人物、长线剧情、章节规划、正文写作、编辑审稿、合规审查、连载状态。所有 Agent 通过 Markdown 项目资料交换信息。

每卷正文开始前，总主编剧 Agent 必须创建 `outline/vol-XX-chapters.md`，写入该卷章节总数、每章名称、一句内容描述、章节功能、节奏规则、关键事件与结尾牵引。章节规划 Agent 与正文写作 Agent 必须依据该 outline 工作，未登记到 outline 的章节不得写作。

## 合规约束

正文、章纲、项目资料不得出现真实地区、国家、省份、城市、领导人、名人名称。现实对象必须使用虚构别名，替代关系保存到 `templates/alias_registry.md` 或项目内同名文件。

## 文件

- `README.md`：资料包说明。
- `agent-system/system-prompt.md`：主系统提示词。
- `agent-system/team.md`：Agent 团队职责。
- `agent-system/workflow.md`：全流程规范。
- `agent-system/compliance.md`：合规名称规则。
- `templates/`：项目资料模板。
- `templates/volume_outline.md`：卷级章节总纲模板。
