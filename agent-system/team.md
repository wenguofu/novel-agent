# Agent 团队索引

## 标准交付物格式

所有 Agent 间传递的交付物使用以下统一结构：

```yaml
delivery:
  agent: <Agent 名称>
  target: <接收 Agent 名称>
  timestamp: <ISO 时间戳>
  refs: <引用文件路径列表>
  content:
    <按各 Agent schema 定义的结构化内容>
```

**跨文件传递规则**：
- 文件路径使用相对于项目根目录的相对路径。
- `refs` 列出本交付物生成过程中加载的所有文件。
- 正文、审稿、状态等持久化产出直接写入文件，同时在 agent 输出中记录文件路径。

## Agent 索引

| # | Agent | 文件 | 参与的工作流 |
|:---|:---|:---|:---|
| 0 | 写作助手 Agent | `team/agent-assistant.md` | 所有工作流（用户交互层） |
| 1 | 总主编剧 Agent | `team/agent-chief-writer.md` | 新书, 新卷 |
| 2 | 类型规则 Agent | `team/agent-genre-rules.md` | 新书, 新卷 |
| 3 | 世界观设定 Agent | `team/agent-world-settings.md` | 新书, **单章, 续写/批量** |
| 4 | 人物 Agent | `team/agent-characters.md` | 新书, 单章 |
| 5 | 长线剧情 Agent | `team/agent-long-plot.md` | 新书, 新卷 |
| 6 | 章节规划 Agent | `team/agent-chapter-planner.md` | 单章, 续写/批量 |
| 7 | 正文写作 Agent | `team/agent-writing.md` | 单章, 续写/批量 |
| 8 | 编辑审稿 Agent | `team/agent-editor-review.md` | 单章, 续写/批量, 审稿 |
| 9 | 合规审查 Agent | `team/agent-compliance.md` | 新书, 单章, 续写/批量, 审稿 |
| 10 | 连载状态 Agent | `team/agent-status.md` | 单章, 续写/批量, 查询 |
| 11 | 剧情执行跟踪 Agent | `team/agent-plot-tracking.md` | 单章, 续写/批量, 审稿 |

## 工作流与 Agent 加载对照

| 工作流 | 加载的 Agent | 脚本辅助 |
|:---|:---|:---|
| 创建新书 | 0, 1, 2, 3, 4, 9 | `stage_gate.py`, `agent_tracker.py` |
| 创建新卷 | 0, 1, 2, 5 | `stage_gate.py`, `agent_tracker.py` |
| 创建单章 | 0, 2, 3, 4, 6, 7, 8, 9, 10, 11 | `stage_gate.py`, `agent_tracker.py`, `rag_context.py`, `analyze_chapter.py`, `check_compliance.py`, `detect_forbidden_patterns.py`, `validate_review.py`, `rag_index.py` |
| 续写/批量 | 0, 2, 3, 4, 6, 7, 8, 9, 10, 11 | `verify_continuity.py`, `rag_context.py`, `analyze_chapter.py`, `rag_index.py` |
| 审稿 | 0, 8, 9, 11 | `analyze_chapter.py`, `check_compliance.py`, `detect_forbidden_patterns.py`, `validate_review.py` |
| 查询状态 | 0, 10 | - |

> **Agent 定义见 `team/` 目录。工作流定义见 `workflows/` 目录。辅助脚本见 `scripts/` 目录。**

## 审稿升级路径

编辑审稿 Agent 维护 `revision_count` 计数器：
- 同章节连续 3 次「修改」结论 → 升级至写作助手 Agent
- 同章节连续 2 次「重写」结论 → 升级至写作助手 Agent
- 写作助手 Agent 将僵局详情呈现给用户决策
