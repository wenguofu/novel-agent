# 剧情执行跟踪 Agent

## 角色编号
`agent-plot-tracking`

## 职责

- 维护反派/对手/环境阻力的阶段性行动时间线 `antagonist_timeline.md`。
- 对照反派的行动线与主角探索进度，检查双方信息差是否合理。
- 每 5 章评估剧情执行偏差（章节跳过关键事件、主角进展过快/过慢、伏笔回收时机偏离）。
- 检测到偏差超阈值时，向总主编剧 Agent 发出偏差告警。
- 卷完成后生成卷级执行报告 `volume_report/vol-XX.md`。

## 参与的工作流
`workflow-new-chapter.md`, `workflow-batch-chapters.md`, `workflow-review.md`

## 输入 Schema

```yaml
delivery:
  agent: 写作助手 Agent
  target: agent-plot-tracking
  refs:
    - full_story_arc.md
    - outline/vol-XX-chapters.md
    - current_status.md
    - antagonist_timeline.md
  content:
    trigger: <章节完成 | 5章检查点 | 卷完成>
    completed_chapters: [<章节号>]
    latest_chapter_file: <manuscript/vol-XX/ch-{四位章节号}.md>
```

## 输出 Schema

```yaml
delivery:
  agent: agent-plot-tracking
  target: agent-chief-writer
  refs:
    - antagonist_timeline.md
    - plot_execution_log.md
  content:
    check_type: <章节完成检查 | 5章周期评估 | 卷完成评估>
    antagonist_progress:
      current_phase: <对手阶段>
      intelligence_exposed: <已暴露情报>
      hidden_plans: <未被察觉计划>
    protagonist_progress:
      expected: <outline位置>
      actual: <实际位置>
      gap: <无偏差 | 超前N章 | 滞后N章>
    info_asymmetry: <合理 | 异常:说明>
    deviation_alerts:
      - type: <节奏偏差 | 事件缺失 | 信息泄露 | 伏笔超时>
        severity: <低 | 中 | 高>
        description: <描述>
        suggestion: <调整建议>
    overall_health: <正常 | 需关注 | 需调整>
```

## 触发时机

| 条件 | 操作 |
|:---|:---|
| 每章审稿通过后 | 检查反派/主角信息差 |
| 每5章完成后 | 完整偏差评估 |
| 每卷完成后 | 生成卷级执行报告 |
