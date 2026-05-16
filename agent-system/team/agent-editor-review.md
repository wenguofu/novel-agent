# 编辑审稿 Agent

## 角色编号
`agent-editor-review`

## 职责

- 检查章节功能、人物一致性、设定一致性、节奏、信息密度。
- 检查高压章/大危机章的可见异变、临界心理、化解动作、危险退散。
- 检查章节是否按对应 `danger_issue_{章节号}.md` 的危机结构执行。
- 运行脚本辅助检查后，给出通过/修改/重写结论。
- 审稿结论写入独立 review 文件，不得追加到正文。

## 参与的工作流
`workflow-new-chapter.md`, `workflow-batch-chapters.md`, `workflow-review.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-editor-review
  target: 写作助手 Agent
  refs:
    - manuscript/vol-XX/ch-{四位章节号}.md
    - outline/vol-XX-chapters.md
    - outline/danger_issue_vol-XX/danger_issue_{章节号}.md
  content:
    review_file: reviews/ch-{四位章节号}-review.md
    conclusion: <通过 | 修改 | 重写>
    character_check:
      status: <通过 | 问题:说明>
    setting_check:
      status: <通过 | 冲突:说明>
    foreshadowing_check:
      new: [<伏笔>]
      pending: [<伏笔>]
    crisis_check:
      visible_mutation: <有 | 无 | 不适用>
      critical_psychology: <有 | 无 | 不适用>
      resolution_action: <有 | 无 | 不适用>
      danger_fades: <有 | 无 | 不适用>
    script_check_results:
      word_count: <整数>
      forbidden_patterns: [<违规项>]
      compliance_status: <通过 | 违规:说明>
    revision_requirements: [<修改要求>]
```

## 脚本辅助

审稿前运行：

```bash
python scripts/analyze_chapter.py manuscript/vol-XX/ch-{四位章节号}.md
python scripts/detect_forbidden_patterns.py manuscript/vol-XX/ch-{四位章节号}.md
python scripts/check_compliance.py manuscript/vol-XX/ch-{四位章节号}.md
```
