---
agent_id: agent-status
display_name: 连载状态
schema_version: "2.0"
prerequisites:
  - current_status.md
  - manuscript/vol-XX/ch-XXXX.md
outputs:
  - state/current_status.md
signatures:
  - 连载状态|current_status
  - 当前(?:剧情|状态)
  - 资料更新|状态更新
severity_levels:
  error: [prerequisites]
  warning: [signatures, schema_fields]
  info: [content_heuristics]
stage: phase7_status_update
---

# 连载状态 Agent

## 角色编号
`agent-status`

## 职责

- 维护 `state/current_status.md`。
- 每写完一章后，立即将剧情位置、人物状态、设定变化、伏笔变化写入。
- 卷完成后更新 `volume_plan/vol-XX.md` 和 `volume_plan.md` 索引。
- 为连续写作提供上下文状态基座。

## 参与的工作流
`workflow-new-chapter.md`, `workflow-query-status.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-status
  target: 写作助手 Agent
  refs:
    - current_status.md
    - manuscript/vol-XX/ch-{四位章节号}.md
    - reviews/ch-{四位章节号}-review.md
  content:
    status_file: state/current_status.md
    current_chapter: <最新章节号>
    status_summary:
      plot_position: <剧情位置>
      character_states: <人物状态汇总>
      setting_updates: <设定更新>
      foreshadowing_updates: <伏笔更新>
    volume_update_needed: <是 | 否>
    if_volume_complete:
      volume_file: volume_plan/vol-XX.md
      actual_structure: <实际卷内结构>
      pending_items: <待完成事项>
```
