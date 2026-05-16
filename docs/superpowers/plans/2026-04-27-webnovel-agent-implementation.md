# 长篇网文 Agent 实施计划

> **给执行 Agent：** 必须使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，按任务逐项执行。步骤使用复选框语法记录状态。

**目标：** 建立一套基于 Markdown 的长篇网文多 Agent 写作体系。

**架构：** 体系以文档为主。Agent 提示词、团队角色、流程规则、合规规则、项目模板分别保存为独立 Markdown 文件。小说项目复制模板后，在写作过程中持续更新资料。

**技术形态：** Markdown 文件、本地文件系统、平台无关 Agent 提示词。

---

### 任务 1：创建资料包说明

**文件：**
- 创建：`README.md`

- [x] **步骤 1：创建说明文件**

创建 `README.md`，写入资料包用途、目录结构、使用方式与关键约束。

- [x] **步骤 2：验证说明文件**

执行：`rg --files`
预期：输出包含 `README.md`。

### 任务 2：创建 Agent 系统文档

**文件：**
- 创建：`agent-system/system-prompt.md`
- 创建：`agent-system/team.md`
- 创建：`agent-system/workflow.md`
- 创建：`agent-system/compliance.md`

- [x] **步骤 1：创建系统提示词**

创建主提示词，包含目标、项目资料读取次序、最高优先级规则、输出结构与角色协作次序。

- [x] **步骤 2：创建团队角色**

创建总主编、类型规则、世界观、人物、长线剧情、章节规划、正文写作、编辑审稿、合规审查、连载状态等角色定义。

- [x] **步骤 3：创建流程**

创建从开书到状态更新的完整写作流程。

- [x] **步骤 4：创建合规规则**

创建真实地名、国家名、省份名、城市名、领导人名、名人名禁用规则，并要求使用别名。

### 任务 3：创建项目模板

**文件：**
- 创建：`templates/project.md`
- 创建：`templates/genre_bible.md`
- 创建：`templates/world_bible.md`
- 创建：`templates/characters.md`
- 创建：`templates/full_story_arc.md`
- 创建：`templates/volume_plan.md`
- 创建：`templates/chapter_packet.md`
- 创建：`templates/chapter_review.md`
- 创建：`templates/current_status.md`
- 创建：`templates/alias_registry.md`

- [x] **步骤 1：创建模板**

创建项目总档案、类型规则、世界观、人物、长线剧情、分卷规划、章节生产包、审稿记录、当前状态、别名表模板。

- [x] **步骤 2：验证模板**

执行：`rg --files templates`
预期：输出包含十个模板文件。

### 任务 4：创建设计与计划记录

**文件：**
- 创建：`docs/superpowers/specs/2026-04-27-webnovel-agent-design.md`
- 创建：`docs/superpowers/plans/2026-04-27-webnovel-agent-implementation.md`

- [x] **步骤 1：创建设计文档**

创建设计记录，包含范围、架构、合规约束与文件说明。

- [x] **步骤 2：创建实施计划**

创建本计划记录，并标记已完成的任务。
