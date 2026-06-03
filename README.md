# Novel Agent — AI 长篇网文写作系统

AI-assisted Chinese web novel writing system (1M-3M words). Flask + React portal with multi-agent architecture, unified database, and MySQL support.

## 快速启动

```bash
cd portal
pip install -r ../requirements.txt

# SQLite (开发)
python run_v2.py
# → http://127.0.0.1:35001

# MySQL (生产)
DATABASE_URL=mysql+pymysql://user:pass@host:3306/novel_agent python run_v2.py
```

## 架构概览 (v3.3)

| 层 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript, Ant Design 5, Vite, Zustand, TanStack Query |
| 后端 | Python Flask, SQLAlchemy ORM, httpx |
| 数据库 | SQLite (dev) / MySQL (prod) — 通过 `DATABASE_URL` 切换 |
| AI | DeepSeek API (chat + SSE streaming) |
| RAG | ChromaDB + BAAI/bge-small-zh-v1.5 |
| 端口 | 35001 |

### 数据库：统一单库架构
24 张表统一在一个数据库，不再分离 content/config/usage。数据访问通过 Repository 模式（`repository.py`），110+ 方法覆盖全部 CRUD。

全文搜索使用 LIKE（MySQL 兼容），已移除 FTS5。

### 核心流程
1. **初始化** → `init_all_from_files()` 从 markdown/yaml 文件加载全部数据
2. **写作** → 12 层上下文组装 + DeepSeek SSE 流式生成
3. **审稿** → AI 审稿 + 脚本合规检查（字数/违禁词/句式）
4. **状态更新** → `auto_update_after_save()` 自动更新角色出场/伏笔状态

### 12 层上下文架构（写作 Prompt）

`portal/context_builder.py` 按预算加载所有可用 DB 资源，组装成 12 层 system prompt。详见 [openspec/specs/context-builder.md](openspec/specs/context-builder.md)。

| # | 名称 | tok | 来源 |
|---|------|-----|------|
| 0 | 核心指令 | 500 | `prompts/core_instructions.j2`（jinja2） |
| 1 | 项目元信息 | 500 | `novels` 行 + 全部 `project_meta` keys |
| 2 | 章节上下文 | 800 | 卷纲 + danger_issue + 上一章结尾 |
| 2.5 | 类型规则 | 500 | 24 条 `genre_rules` 按 `rule_category` 分组（🔴必须/🟡可选） |
| 3 | 角色上下文 | 2000 | `characters` + `novels/{name}/characters.md` 字段缺失时 fallback |
| 4 | 伏笔待办 | 1000 | 当前卷未填坑伏笔 |
| 5 | 世界观 | 1500 | 本卷 5 条 + 后续卷 5 条（[本卷] / [全局] 标签） |
| 6 | 节奏情感 | 500 | `pacing_control`（per chapter） |
| 7 | 信息释放 | 500 | `revelation_schedule` |
| 8 | 剧情弧线 | 1000 | `plot_arcs` |
| 8.5 | 禁用词与合规 | 200 | `banned_words` + `compliance_rules`（config DB） |
| 9 | 写作风格 | 500 | `style_presets.prompt` + `novels/{name}/style.md` + `agent-system/styles/{author}.json` 指纹 |

**合计 9500 tok 分配 + 500 tok 弹性（cap 10000）**

关键设计（2026-06-02 优化）：
- **风格名解析**：前端传 `style: "辰东风 50%, 默认 50%"`，后端解析成 实际 prompt 内容 + 风格指纹（句长直方图、对话比、转折词密度）
- **生成端合规约束**：禁用词 + 合规规则从"事后检查"升级为"事前注入 prompt"，LLM 在生成阶段就看到约束
- **人物/世界兜底**：DB 字段稀疏时自动从 `characters.md` 读富源；世界观不只读本卷，还加 5 条跨卷设定
- **core_instructions 单一来源**：jinja2 模板 + Python 兜底

## TDD 流程

`portal/` 改动必须同时改 `tests/`。物理门**计划在 M3**（`tdd-required-test` hook，见 spec §M3）。
豁免: commit 标题含 `hotfix`。
基线: `pytest tests/ -q` 当前 0 failed / 0 errors (维护自 2026-06-03, 见 `tests/audit/baseline_after.json`)。
审计工具: `python3 scripts/audit_test_failures.py` 重跑确认 0 失败。

## 文件结构

```text
novel-agent/
├── portal/                     # Web 应用
│   ├── app.py                  # Flask 路由 (40+ endpoints)
│   ├── run_v2.py               # 启动器 (schema init + config seed + 启动)
│   ├── db.py                   # SQLAlchemy engine/session (SQLite/MySQL)
│   ├── models_orm.py           # 26 ORM 模型
│   ├── repository.py           # Repository 层 (110+ 方法)
│   ├── content_db.py           # 兼容层 → 委托给 repository
│   ├── context_builder.py      # 12 层上下文组装
│   ├── init_config_db.py       # [已废弃] → init_unified_db.py
│   ├── rag_engine.py           # RAG 检索引擎
│   ├── state_tracker.py        # 状态变更追踪
│   ├── memory_layer.py         # 记忆层 (ChromaDB + DB fallback)
│   └── frontend/               # React SPA
├── agent-system/               # 多 Agent 写作体系
│   ├── team/                   # 12 个 Agent 角色定义 (YAML frontmatter)
│   ├── workflows/              # 工作流定义
│   ├── scripts/                # 检测/分析/合规脚本
│   └── styles/                 # 16 种风格指纹
├── novels/<name>/              # 小说项目目录
│   ├── project.md              # 项目设定
│   ├── genre_bible.md          # 类型规则
│   ├── world_bible.md          # 世界观
│   ├── characters.md           # 人物档案
│   ├── full_story_arc.md       # 全书剧情线
│   ├── alias_registry.md       # 别名注册表
│   ├── outline/                # 卷大纲 (YAML/MD)
│   ├── manuscript/             # 正文手稿
│   ├── reviews/                # 审稿报告 (MD + JSON)
│   ├── volume_plan/            # 卷规划
│   └── state/                  # 运行状态 (stage_gate.json, current_status.md)
├── openspec/                   # 架构文档
├── tests/                      # 119 pytest 测试
└── scripts/                    # 迁移/升级脚本
```

## API 端点 (主要)

> 完整 83 端点字段级参考（含 Manual Notes、Repo 方法、读写表）见
> [docs/system-functional-spec.md](docs/system-functional-spec.md)。
> 数据驱动：跑 `python3 scripts/inventory_endpoints.py && python3 scripts/render_spec.py` 重新生成。
> CI 校验：跑 `python3 scripts/verify_spec.py`（5 项一致性检查）。

### 写作与生成
| 端点 | 说明 |
|------|------|
| `POST /api/context/build` | 12 层上下文组装 |
| `POST /api/ai/stream` | SSE 流式调用 DeepSeek |
| `POST /api/novels/<name>/generate-chapter` | 服务端章节生成 |
| `POST /api/novels/<name>/review-chapter` | AI 审稿 + 脚本检查 |

### 领域 CRUD (全部 RESTful)
characters, foreshadowing, world_building, plot_arcs, pacing_control, revelation_schedule, genre_rules, story_volumes, volume_plans, alias_names, project_meta

### 配置与统计
- `GET/POST /api/config` — DeepSeek 配置
- `/api/config-db/<table>` — 违禁词/合规规则/风格预设 CRUD
- `GET /api/usage/stats` — Token 用量统计
- `GET /api/content/search?q=` — 全文搜索

## 使用方式

1. 创建小说项目目录，填写 `project.md`、`genre_bible.md`、`characters.md` 等
2. 启动 portal：`cd portal && python run_v2.py`
3. 打开 http://127.0.0.1:35001 → 选择小说 → 写作页生成章节
4. 或通过 API 直接调用：`POST /api/novels/<name>/generate-chapter`

## 关键约束

- 每本书：独立类型规则、人物档案、世界观、长线剧情、别名表
- 每卷：独立章纲 (YAML/MD)，正文遵守 outline 条目
- 正文：不得使用真实地名/人名/产品名，违规词自动替换
- 伏笔/状态变化必须写入项目资料
- 审稿连续 3 次修改或 2 次重写 → 自动升级至用户决策

## 合规规则自定义

编辑 `agent-system/compliance_config.json` 可自定义：
- `real_name_patterns`：检测的真实名称列表
- `alias_suggestions`：违规时建议的替换别名
- `context_sensitivity`：不触发违规的上下文白名单 |
