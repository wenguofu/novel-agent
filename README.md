# 长篇网文写作 Agent 资料包

本目录提供一套面向 100 万到 300 万字网文项目的多 Agent 写作体系。体系采用 Markdown 管理项目资料，适用于本地文件夹，也适用于任何支持多角色提示词的工具。

## 文件结构

```text
agent-system/
  system-prompt.md
  team.md
  workflow.md
  compliance.md
templates/
  project.md
  genre_bible.md
  world_bible.md
  characters.md
  full_story_arc.md
  volume_plan.md
  volume_outline.md
  chapter_packet.md
  chapter_review.md
  current_status.md
  alias_registry.md
docs/superpowers/
  specs/
  plans/
```

## 使用方式

1. 复制 `templates/` 为某本书的项目目录。
2. 填写 `project.md`、`genre_bible.md`、`world_bible.md`、`characters.md`。
3. 将 `agent-system/system-prompt.md` 放入主 Agent 的系统提示词。
4. 每卷正文开始前，创建 `outline/vol-XX-chapters.md`，写入章节总数、章节名、一句内容描述与节奏规则。
5. 每章写作必须经过章节规划、正文写作、编辑审稿、合规审查、状态更新。

## 关键约束

- 每本书必须有独立类型规则、人物档案、世界观资料、长线剧情表、别名表。
- 每卷必须有独立卷级章纲，正文写作必须遵守对应 outline 条目。
- 正文不得使用真实地区、国家、省份、城市、领导人、名人名称。
- 现实对象必须用虚构别名替代，且替代关系写入 `alias_registry.md`。
- 任何新增设定、人物状态变化、伏笔变化都必须写入项目资料。
