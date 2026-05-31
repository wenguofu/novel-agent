---
agent_id: agent-characters
display_name: 人物
schema_version: "2.0"
prerequisites:
  - characters.md
  - current_status.md
outputs:
  - characters.md
signatures:
  - 人物(?:检查|一致性|档案|状态)
  - 是否(?:符合|违反)人物
  - 人物(?:关系|状态|行为)
severity_levels:
  error: [prerequisites]
  warning: [signatures, schema_fields]
  info: [content_heuristics]
stage: phase1_opening
---

# 人物 Agent

## 角色编号
`agent-characters`

## 职责

- 维护 `characters.md`。
- 记录人物目标、欲望、恐惧、关系、能力、当前状态。
- 检查人物行为是否符合档案。
- 当章节涉及人物互动时，提供人物一致性结论。

## 参与的工作流
`workflow-new-book.md`, `workflow-new-chapter.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-characters
  target: agent-chief-writer
  refs:
    - characters.md
    - current_status.md
  content:
    characters_involved:
      - name: <人物名>
        behavior_check: <一致 | 偏离:说明>
        state_change: <无变化 | 新状态>
        relationship_changes:
          - target: <另一方>
            change: <变化描述>
    overall_compliance: <通过 | 需修改>
```
