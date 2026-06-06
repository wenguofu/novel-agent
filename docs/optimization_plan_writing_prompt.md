# 写作接口 Prompt 优化计划

> 创建于 2026-06-02，基于对 `api_generate_chapter` 调用链路的完整审计。

## 目标

把 9-layer 上下文系统从"漏关键内容"修复为"按预算加载全部可用 DB 资源"，
让 LLM 拿到足以写出符合设定/风格/规则的章节所需的全部信息。

## 调用链

```
前端 _getWritingStyleStr ("辰东风 50%")
   ↓
app.py:1668 api_generate_chapter
   ↓
context_builder.build_context (9 layer, 10000 tok budget)
   ↓
deepseek_chat(system_prompt=..., user="请创作 vol-01 第 001 章")
```

## 当前各 layer 状态

| Layer | 名称 | DB 资源 | 当前加载 | 问题 |
|---|---|---|---|---|
| 0 | 核心指令 | 硬编码+jinja2 | ✓ 全部 | 双源不一致 |
| 1 | 项目元信息 | novels + project_meta (14 keys) | ✗ 只读 novels 3 字段 | project_meta 完全漏 |
| 2 | 章节上下文 | outlines + danger_issues + chapters | ⚠ 部分 | danger 800 字截断太狠 |
| 3 | 角色上下文 | characters (12 rows) | ⚠ 浅 | 只取 4 字段各 200 字，background/arc 全空 |
| 4 | 伏笔待办 | foreshadowing | ✓ OK | — |
| 5 | 世界观 | world_building (41 rows) | ⚠ 部分 | 按当前卷过滤 + 200 字截断 |
| 6 | 节奏情感 | pacing_control | ✓ OK | — |
| 7 | 信息释放 | revelation_schedule | ✓ OK | — |
| 8 | 剧情弧线 | plot_arcs (17 rows) | ⚠ 部分 | 200 字截断太狠 |
| 9 | 写作风格 | style_presets (5 rows) + distilled JSON (15 files) + style.md | ❌ **只传名字** | **核心 bug** |

## 缺失资源（DB 里有，prompt 里没有）

- `style_presets.prompt`：5 行有具体描述（如"以辰东风格写作：宏大的世界观设定..."）—— **完全没读取**
- `agent-system/styles/*.json`：15 个作家指纹（句长直方图、对话比、转折词密度）—— **完全没读取**
- `style.md`（小说专属混合风格，5252 字节）—— **完全没读取**
- `project_meta`：14 个 key-value（乐园、八位古神、叛神系统等核心设定，601 字符）—— **完全没读取**
- `genre_rules`：24 条类型规则（必须元素/节奏规则/读者期待管理，686 字符）—— **生成端完全没读**（review 端有读）
- `banned_words`：20 行 —— **生成端没读**（仅事后检查）
- `compliance_rules`：4 行 —— **生成端没读**（仅事后检查）
- `characters.md` (21KB) —— 生成端没读，**但因 DB background 列空，这是唯一富源**（应作 fallback）
- `world_bible.md` (21KB) —— 生成端没读，**但因 DB 只存摘要，这是富源**
- `genre_bible.md` (4KB) —— 生成端没读，**但 DB 已有 genre_rules，这只是冗余备份**

## 优化方案

### P0（核心 bug）

#### P0-1: Layer 9 解析风格名 → 加载 preset.prompt
- 输入：`"辰东风 50%, 默认 50%"`
- 输出：把每个名字解析为 `style_presets.prompt` 内容，按百分比分配 token
- 实现：`_build_style_context` 增加 `novel_name` 参数，调用 `db.get_style_preset_by_name()`

#### P0-2: 加载小说专属 `style.md`
- 路径：`novels/{name}/style.md`
- 存在则优先于 global preset
- 分配 token：~500 字

### P1（必须）

#### P1-1: 新增 `genre_rules` Layer
- 编号：Layer 3.5（在角色后、伏笔前）
- token 预算：500
- 内容：把 24 条规则按 `rule_category` 分组展示

#### P1-2: 新增 `banned_words + compliance_rules` Layer
- 编号：Layer 8.5（在剧情弧线后、风格前）
- token 预算：200
- 内容：列出禁用词 + 合规规则关键约束

#### P1-3: Layer 1 加载全部 `project_meta`
- 当前：3 字段
- 优化：14 个 key-value 全部加载，token 预算从 300 → 500

### P2（强烈建议）

#### P2-1: Layer 9 增强 — 加载 distilled JSON 指纹
- 解析 `agent-system/styles/{author}.json`
- 提取：`sentence_length_mean`, `dialogue_ratio`, `vocabulary_richness`, `transitions` (top 5), `sentence_openers` (top 3)
- 拼成结构化风格指纹注入 prompt

#### P2-2: Layer 3 fallback — 缺字段时读 `characters.md`
- 当 `characters.background/arc/lifeline` 为空
- 解析 `characters.md` 中对应人物的 markdown 段
- 用段落作为补充

#### P2-3: Layer 5 取消按当前卷过滤
- 当前：`get_world_building_for_volume(vol, limit=10)` 排除 later vol
- 优化：先按当前卷取 5 条 + 全局取 5 条（重要设定如八神体系不丢）

### P3（清理）

#### P3-1: 统一 core_instructions 来源
- 删除 `context_builder.py:31-45` 硬编码字符串
- 改为 `render_prompt("core_instructions")` 加载 jinja2 模板

#### P3-2: 调整 token 预算

旧分配（10000 总）：
```
Layer 0:  500
Layer 1:  300
Layer 2:  800
Layer 3: 2000
Layer 4: 1500
Layer 5: 1500
Layer 6:  500
Layer 7:  500
Layer 8: 1000
Layer 9:  500  ← 风格
合计:  9100 (留 900 弹性)
```

新分配（10000 总）：
```
Layer 0:   500  核心指令
Layer 1:   500  项目元信息 (+project_meta 14 keys)
Layer 2:   800  章节上下文
Layer 2.5: 500  genre_rules (新)
Layer 3:  2000  角色 (含 characters.md fallback)
Layer 4:  1000  伏笔 (略减)
Layer 5:  1500  世界观 (含 later vol)
Layer 6:   500  节奏情感
Layer 7:   500  信息释放
Layer 8:  1000  剧情弧线
Layer 8.5:  200  banned + compliance (新)
Layer 9:   500  风格 (style_presets + style.md)
合计:    9500 (留 500 弹性)
```

## 实施顺序

1. P0-1 + P0-2：解决核心风格 bug
2. P1-1 + P1-2 + P1-3：补齐必备约束
3. P2-1 + P2-3：增强风格指纹和世界观覆盖
4. P2-2：人物档案 fallback
5. P3-1 + P3-2：清理双源 + 重分配预算

## 测试计划

- 新增 `test_context_layers.py`：对每个 layer 写"输入 → 输出"快照测试
- 跑 `pytest tests/ -q` 确保不破坏 baseline（22 failed 是预存的，与本次无关）
- 手动检查：跑 `python -c "from context_builder import build_context; ..."` 看实际 prompt

## 涉及文件

| 文件 | 改动 |
|---|---|
| `portal/context_builder.py` | 主战场（9 layer + 新增 3 layer） |
| `portal/content_db.py` | 新增 `get_style_preset_by_name()`, `get_novel_style_md()` 等辅助函数 |
| `portal/prompts/core_instructions.j2` | 唯一来源（删除硬编码副本） |
| `tests/test_context_layers.py` | 新增 layer 单测 |
