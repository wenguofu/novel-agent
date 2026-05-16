# 正文写作 Agent

## 角色编号
`agent-writing`

## 职责

- 根据章纲和风格指令生成正文。
- 每个写作回合先加载 `state/current_status.md`，确认上一章结尾状态。
- 必须引用 outline 对应条目，正文服务章节功能、关键事件与结尾牵引。
- 未在 outline 登记的章节不得写作。
- 高压章/大危机章必须写出可见异变、队伍被牵入过程、临界心理。
- 主角化解危机必须有清楚动作，动作后危险画面必须退散或停止。
- 写作完成后运行 `scripts/analyze_chapter.py` 验证字数和不合格模式。

## 参与的工作流
`workflow-new-chapter.md`, `workflow-batch-chapters.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-writing
  target: agent-editor-review
  refs:
    - outline/vol-XX-chapters.md
    - outline/danger_issue_vol-XX/danger_issue_{章节号}.md
    - current_status.md
  content:
    chapter_file: manuscript/vol-XX/ch-{四位章节号}.md
    word_count: <整数>
    style_applied: <已应用的风格>
    new_settings_introduced:
      - name: <设定名>
        category: <物品|地点|规则>
    character_state_changes:
      - name: <人物名>
        change: <变化描述>
    foreshadowing_changes:
      added: [<伏笔>]
      triggered: [<伏笔>]
```

## 脚本辅助

正文写作 Agent 在输出前运行以下脚本做自检：

```bash
python scripts/analyze_chapter.py manuscript/vol-XX/ch-{四位章节号}.md
python scripts/detect_forbidden_patterns.py manuscript/vol-XX/ch-{四位章节号}.md
```

- `analyze_chapter.py`：统计中文字数，检查结构合规（无元数据段/总结段）
- `detect_forbidden_patterns.py`：检测二元对照句式超过2次、重复对话等
