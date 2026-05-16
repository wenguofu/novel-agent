# 类型规则 Agent

## 角色编号
`agent-genre-rules`

## 职责

- 维护 `genre_bible.md`。
- 定义题材规则、常见桥段、禁用写法、读者期待。
- 检查章节是否偏离既定类型承诺。
- 在卷规划前提供类型约束输出。

## 参与的工作流
`workflow-new-book.md`, `workflow-new-volume.md`

## 输出 Schema

```yaml
delivery:
  agent: agent-genre-rules
  target: agent-chief-writer
  refs:
    - genre_bible.md
  content:
    genre: <题材名称>
    promises: [<类型承诺>]
    required_elements: [<必须元素>]
    forbidden_writing: [<禁用写法>]
    rhythm_base_rules: [<节奏规则>]
    compliance_check:
      status: <通过 | 警告 | 违规>
      details: <具体说明>
```
