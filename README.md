# 长篇网文写作 Agent 资料包

本目录提供一套面向 100 万到 300 万字网文项目的多 Agent 写作体系。体系采用 Markdown 管理项目资料，适用于本地文件夹，也适用于任何支持多角色提示词的工具。

## 文件结构

```text
agent-system/
  compliance_config.json   ← 合规检测规则配置（可编辑！）
  system-prompt.md
  team.md
  compliance.md
  team/
    agent-assistant.md     ← 用户交互层（新增）
    agent-chief-writer.md
    agent-chapter-planner.md
    agent-writing.md
    agent-editor-review.md  ← 新增升级机制
    agent-compliance.md
    agent-characters.md
    agent-genre-rules.md
    agent-world-settings.md  ← 新增参与单章工作流
    agent-long-plot.md
    agent-plot-tracking.md
    agent-status.md
  scripts/
    analyze_chapter.py
    check_compliance.py      ← v2: 使用外部配置
    detect_forbidden_patterns.py  ← v2: 改进重复检测
    verify_continuity.py
  workflows/
    workflow-new-chapter.md  ← 新增世界观审核+升级机制
    workflow-batch-chapters.md  ← 新增两阶段模式+升级机制
    workflow-new-book.md
    workflow-new-volume.md
    workflow-review.md
    workflow-query-status.md
  writer-style-skill.md      ← 31位作家风格指南
  writing-assistant.md
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
5. 每章写作必须经过章节规划、正文写作、编辑审稿、世界观设定审核、合规审查、状态更新。
6. 合规检查规则位于 `agent-system/compliance_config.json`，可根据需要编辑。

## 关键约束

- 每本书必须有独立类型规则、人物档案、世界观资料、长线剧情表、别名表。
- 每卷必须有独立卷级章纲，正文写作必须遵守对应 outline 条目。
- 正文不得使用真实地区、国家、省份、城市、领导人、名人名称。
- 现实对象必须用虚构别名替代，且替代关系写入 `alias_registry.md`。
- 任何新增设定、人物状态变化、伏笔变化都必须写入项目资料。
- 编辑审稿连续 3 次修改或 2 次重写则自动升级至用户决策。

## 合规规则自定义

编辑 `agent-system/compliance_config.json` 可自定义：
- `real_name_patterns`：检测的真实名称列表（国家、省份、城市、领导职务）
- `alias_suggestions`：检测到违规时建议的替换别名
- `context_sensitivity`：不触发违规的上下文白名单

## 新增功能（v2）

| 改进 | 说明 |
|:---|:---|
| 📋 合规配置化 | 检测规则从 compliance_config.json 读取，可自由增删 |
| 🗺️ 完整地名覆盖 | 31省+所有地级市+200+县级市映射 |
| 🧠 上下文白名单 | "小说中""虚构的"等语境不触发违规 |
| 🔄 审稿升级机制 | 3次修改/2次重写自动升级到用户 |
| 🌍 世界观审核 | 单章新增设定自动校验 world_bible.md |
| 🎭 对话重复改进 | 最长公共子串≥15字才算重复，减少误报 |
| ⚡ 批量效率优化 | 两阶段模式+状态传递优化 |
| 🧑‍💼 写作助手 Agent | 明确定义用户交互层角色 |
