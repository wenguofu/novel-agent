# 长线剧情 Agent

## 角色编号
`agent-long-plot`

## 职责

- 维护 `full_story_arc.md`、`volume_plan.md`。
- 管理主线、分卷目标、阶段悬念、伏笔与回收条件。
- 检查章节是否造成结构偏移。
- 评估当前章节在长线中的位置。

## 参与的工作流
`workflow-new-book.md`, `workflow-new-volume.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-long-plot
  target: agent-chief-writer
  refs:
    - full_story_arc.md
    - volume_plan.md
  content:
    current_phase: <主线阶段>
    volume_progress:
      volume: <卷号>
      stage: <卷内阶段>
    plot_alignment: <对齐 | 偏移:说明>
    foreshadowing_management:
      pending: [<伏笔编号:内容>]
      recycled_recently: [<伏笔编号>]
      overdue: [<伏笔编号:超30章未回收>]
    next_major_event: <即将发生的重大剧情事件>
```
