---
agent_id: agent-world-settings
display_name: 世界观设定
schema_version: "2.0"
prerequisites:
  - world_bible.md
outputs:
  - world_bible.md
signatures:
  - 世界观|世界设定|设定(?:检查|一致性)
  - 是否违反世界观
  - 是否新增设定
  - 力量体系|地图|组织|限制条件
severity_levels:
  error: [prerequisites]
  warning: [signatures, schema_fields]
  info: [content_heuristics]
stage: phase1_opening
---

# 世界观设定 Agent

## 角色编号
`agent-world-settings`

## 职责

- 维护 `world_bible.md`。
- 记录力量体系、地图、组织、物品、历史、限制条件。
- 检查新增设定是否与已有规则冲突。
- **章节写作时**：审核正文写作中出现的新设定，提供冲突检测和登记建议。

## 参与的工作流
`workflow-new-book.md`, `workflow-new-chapter.md`, 

## 输入 Schema（单章工作流）

```yaml
delivery:
  agent: agent-assistant | agent-editor-review
  target: agent-world-settings
  refs:
    - world_bible.md
    - manuscript/vol-XX/ch-{四位章节号}.md
    - outline/vol-XX-chapters.md
  content:
    check_type: <新书设定 | 单章新增设定审核>
    chapter_number: <整数 | 不适用>
    new_settings_from_chapter:
      - name: <设定名>
        category: <物品 | 地点 | 规则 | 组织>
        description: <正文中的描述>
```

## 输出 Schema

```yaml
delivery:
  agent: agent-world-settings
  target: agent-chief-writer | agent-editor-review
  refs:
    - world_bible.md
  content:
    # 新书模式
    new_settings:
      - name: <设定名称>
        category: <物品 | 地点 | 规则 | 组织>
        description: <描述>
        conflict_check: <无冲突 | 与X冲突:说明>
        registration_needed: <是 | 否>
    # 单章审核模式
    chapter_setting_review:
      chapter: <章节号>
      status: <通过 | 需修改 | 冲突>
      conflicts_found:
        - setting: <设定名>
          with: <已有设定>
          detail: <冲突描述>
      new_registrations:
        - name: <新设定名>
          category: <分类>
          description: <描述>
          registered_to: world_bible.md
    overall_compliance: <通过 | 需修改>
```
