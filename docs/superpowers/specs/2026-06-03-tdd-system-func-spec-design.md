# TDD + System Functional Spec — Design

> Date: 2026-06-03
> Status: Draft (awaiting user review)
> Goal: 把当前 agent 的全部功能写成「机器可校验的全量 API 文档」+「TDD 强制流程」+「agent 自动 code review 闭环」,并使 baseline 测试从 22 failed + 15 errors 修到 0。

---

## 0. 范围 / 非范围

**In scope**
- 一份全量 API 文档（80 endpoints, 含源码反推）
- 一组功能测试用例（每 endpoint ≥ 4 维度）
- 1 个 pre-commit 物理门（portal 改动必须带 tests 改动）
- 1 个 agent-as-reviewer hook（commit 后自动跑 6 维 review,发现问题自动喂回 agent 修）
- 1 个 line coverage ≥ 90% 门槛
- 1 个月度文档漂移检测

**Out of scope（明确不做）**
- 不重写 OpenSpec 现有 7 个 spec 文件
- 不重写 README（只在 TDD 章节加一段, 独立 PR）
- 不画架构图
- 不写业务背景
- 不强制 Conventional Commits
- 不引 mutation testing
- 不做 xfail 90 天复活规则（用户已剔除）
- 不在 agent.md 里加 hotfix 之外的豁免（hotfix 是唯一豁免关键词）

**与 `openspec/changes/` 现有活跃 change 的关系**
当前活跃 4 个 change:
- `react-antd-portal` / `sidebar-hierarchy` / `sidebar-refactor`（前端 UI 重构, 跟 M1/M2/M3 关系: **无关** — 不影响后端 API 表面, 不动 portal/ 也不动 tests/）
- `writing-prompt-optimization`（2026-06-02 已 apply, 等待归档）

本次设计对它们的处理:
- M1 测试修零: 不动这 4 个 change 目录
- M2 文档: 不重新生成它们的 spec（`openspec/changes/<name>/specs/*` 是 delta, 不是 base spec）
- M3 测试 + pre-commit: **不影响**, 因为 hooks 只看 `portal/` 和 `tests/` 改动
- 月度漂移检测: 仍要校验 `app.py` 端点表; 这 4 个 change 完成后若动了 `app.py`, 由它们各自承担 M2/M3 工作流
- 推荐: 这 4 个 change 归档前先 review, 看 M3 流程是不是要 backfill 到它们的 tasks.md (决策: **不 backfill**, 因为它们已是历史 work)

---

## M1 — 测试基线修零

### 目标
`pytest tests/ -q` 输出 **0 failed + 0 errors**（skip / xfail 允许,但必须带 reason）。

### 失败分类（F1-F4 严格 4 档,无第 5 档）
| 类别 | 处理 | 标记 | 验收 |
|------|------|------|------|
| F1 真 bug | 修实现 + 加回归测试 | 无 | 测试通过且 tests/functional/ 留 1 个对应测试 |
| F2 测试 bug | 修测试 | 无 | 测试通过 |
| F3 依赖外部/环境 | @pytest.mark.skip(reason=...) 或 xfail | 标记 | `pytest -rs` 能看到原因 |
| F4 已废弃 API | 删测试 + docs/deprecated.md 留一笔 | 无 | 文件被 git 删除 |

### 不变量
- **不删实现只为让测试过** — F1 必须找到真 bug,否则归 F4
- **不引入新依赖** — 用现有 pytest + 现有 import
- **审计数据可复现** — `tests/audit/baseline_before.json` 永远不改（与 `baseline_after.json` 并存）

### 工具
- `scripts/audit_test_failures.py`: 扫 `pytest --tb=line`, 输出 `tests/audit/failures.json` + `tests/audit/REPORT.md`
- 输出字段: nodeid / status / file:line / error 摘要 / 建议类别 F1-F4 / 关联源码行

### 步骤
1. 建 `tests/audit/baseline_before.json`（当前 22 failed + 15 errors nodeid 列表）
2. 跑 audit 工具,得 4 类分布
3. 每条按 F1-F4 修,每修一条更新 `baseline_after.json` (status: passed/skipped/xfail/deleted + 原因)
4. 验收: `pytest tests/ -q` 0 failed + 0 errors;before/after 节点数一致

---

## M2 — 系统功能说明文档（全量 API + 源码反推）

### 产出
- `docs/system-functional-spec.md`（80 端点 × 7 字段:URL / Method / Params / Body / Response / Repo methods / Tables）
- 数据驱动, 不手写

### 工具链
1. **提取器** `scripts/inventory_endpoints.py`
   - AST 扫 `portal/app.py`, 抓每个 `@app.route(...)` 装饰的函数
   - 提取: route / methods / func name / docstring 首行 / 函数内 `repo.<method>()` 调用（AST Call 节点名匹配 `get_repo` 后的 `.method_name`）
   - 提取: 函数内 `db.execute()` / `sqlite3` / `session.add()` 表操作（字符串模式匹配）
   - 关联 `repository.py` 方法签名（推断参数 + 返回类型）
   - 输出 `docs/auto-inventory.json`
2. **渲染器** `scripts/render_spec.py`
   - 读 `auto-inventory.json`
   - Jinja2 模板渲染成 `system-functional-spec.md`
   - 模板有 `<!-- MANUAL:{ep} -->` ... `<!-- /MANUAL -->` 占位符, 保留人工补充段
3. **校验脚本** `scripts/verify_spec.py`（CI 跑）
   - `app.py` endpoint 数 == `auto-inventory.json` endpoint 数
   - 每个 endpoint 在 spec.md 有对应小节（按 `# Endpoint: <route>` 锚点匹配）
   - 失败 → exit 1

### 文档结构
```
# Novel Agent — System Functional Spec
> 机器生成 + 人工补充。Source of truth: portal/app.py AST.
> Auto-generated: <ts>. Inventory: 80 endpoints.

## 1. 架构概览
## 2. 数据模型（24 表, 简要）
## 3. Repository 层（110+ 方法, 按表分组）
## 4. 上下文构建（12 层）
## 5. API 端点
### 5.1 写作与生成
#### Endpoint: POST /api/context/build
- Method / Description / Request Body / Response 200 / Repository calls / Tables / Side effects
<!-- MANUAL: POST_/api/context/build -->
(开发者补充)
<!-- /MANUAL -->
```

### Manual Notes 强制范围
**只对约 25 个核心 endpoint 强写 Manual Notes**, 其余可选, CI 不拦。最终数量由 inventory 工具跑出, 文档里只列「估算类别 + 提交时由 inventory 工具筛」:
- 核心 endpoint 定义: 写作/生成/上下文/审稿/库结构变更 这 5 类
- 估算清单（提交时由 inventory 工具自动筛, 5 大类）:
  - 写作与生成类: `/api/ai/stream` `/api/ai/chat` `/api/context/build` `/api/context/stats/...` `/api/novels/<name>/generate-chapter` `/review-chapter` `/optimize-chapter` `/api/novels/create`
  - 章节生命周期类: `/api/novels/<name>/chapters/...` (GET/POST/DELETE/edit)
  - 工作流类: `/api/novels/<name>/update-status` `/enforce-pipeline` `/run-script` `/api/workflow/preflight/...` `/postflight/...` `/api/init/full/...` `/api/rag/query`
  - 库结构变更类: `/api/novels/<name>/world-building/init` 等 4 个 init + 字段 CRUD (characters / foreshadowing / plot_arcs / pacing / revelation / genre_rules / world_building / story_volumes / volume_plans / alias_names / project_meta)

### 失败重生成策略
- `app.py` 改 endpoint 签名 → `auto-inventory.json` 重生成 → spec.md 重渲染 → CI 看 diff 报"endpoint 数量变化",开发者必须 commit 文档
- 旧 Manual Notes 用 `<!-- MANUAL: {ep} -->` 锚点保留, 不被覆盖

---

## M3 — 功能测试用例 + pre-commit 物理门

### 测试目录布局
```
tests/functional/
├── conftest.py                # 共享 fixture (临时 SQLite, Flask client, sample novel)
├── test_writing_api.py        # 写作与生成 (~10)
├── test_chapter_lifecycle.py  # 章节 CRUD + 审稿 (~8)
├── test_novel_management.py   # 小说项目 + 文件操作 (~6)
├── test_domain_crud.py        # characters / foreshadowing / world / arcs / pacing (~30)
├── test_context.py            # 12 层 prompt 装配 (~3)
├── test_workflow.py           # preflight / postflight / enforce-pipeline (~5)
├── test_config_api.py         # DeepSeek config + config-db (~6)
├── test_init.py               # 全量初始化 (~5)
├── test_ai_stream.py          # /api/ai/chat + /api/ai/stream (mock httpx) (~3)
├── test_search.py             # /api/content/search (~2)
└── INTEGRATION.md             # 人类可读总览
```

### 每 endpoint 最小测试维度（4 必含）
| 维度 | 内容 |
|------|------|
| 正常路径 | 200/201 + response schema assertion |
| 缺字段 | 400 + error message 断言 |
| 不存在 | 404 (如 novel_name 不存在) |
| 方法错误 | 405 (GET 改 POST) |

### 共享 fixture (conftest.py)
```python
@pytest.fixture
def tmp_db(tmp_path): ...        # 临时 SQLite, fixture 结束自动清理
@pytest.fixture
def client(tmp_db, monkeypatch): ...  # Flask test client + 改 DATABASE_URL
@pytest.fixture
def sample_novel(client): ...   # 预置大强成神啦 + 14 project_meta + 3 角色 + 2 伏笔 + outline/danger_issue
```

### pre-commit 物理门
`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: tdd-required-test
        name: TDD - portal changes require test changes
        entry: scripts/check_tdd_compliance.sh
        language: script
        files: ^portal/.*\.py$
        pass_filenames: false
        stages: [pre-commit]
```

`scripts/check_tdd_compliance.sh`:
- portal/ 改动 必须 带 tests/ 改动
- tests/ 改动只允许 test_*.py 或 conftest.py
- commit 标题含 `hotfix` → 放行, 其余阻断
- 改 hook 自身（`.pre-commit-config.yaml` / `scripts/check_tdd_compliance.sh`）也受 hook 保护

### Coverage
- `pytest --cov=portal --cov-report=term-missing`
- line coverage ≥ 90% 是 release 门槛
- pre-commit 不跑（耗时）, CI 跑

---

## 持续 — 6 维 Agent Code Review

### 触发
commit 完成 → agent hook 唤起 Claude Code 新会话 → 读 diff → 跑 review → 写 `.code-reviews/<sha>.md` → 该文件存在才允许 push。

### 6 维
1. **Correctness** — 语法 / 边界 / 异常路径
2. **Security** — SQL 注入 / 路径穿越 / 敏感信息泄露
3. **Style** — 命名 / 复杂度 / 重复
4. **Test coverage** — 改动是否有对应 tests
5. **Performance** — 复杂度分析 / DB 查询次数
6. **Docs** — 如果有 spec 变动, README / spec.md 是否同步

### 报告处理
- 报告任何问题 → 触发"优化脚本": 把问题清单丢回 Claude Code → 改代码 → 重 commit
- 循环终止: review 报告 0 问题 或 开发者手动加 `hotfix` 跳过
- 实现位置: `agent-system/scripts/post_commit_review.sh` + `.claude/hooks/post-commit`

---

## 端点添加/删除工作流（持续）

### 添加
1. 在 `portal/app.py` 加 endpoint
2. 跑 `scripts/inventory_endpoints.py` → `auto-inventory.json` 更新
3. 跑 `scripts/render_spec.py` → `system-functional-spec.md` 更新
4. 在 spec.md 对应 Manual Notes 段补内容（25 个核心 endpoint 必写）
5. 在 `tests/functional/` 对应文件加 4+ 测试
6. 跑 `pytest tests/functional/ -q` 全过 + coverage ≥ 90%
7. commit → CR hook 自动跑

### 删除
- 提取器发现 endpoint 数变少 → CI 红 → 开发者同时删 `tests/functional/` 对应测试
- 删的 endpoint 在 spec.md 用 `<!-- DEPRECATED: ... -->` 标记保留 30 天再彻底删

---

## 月度检测

每月 1 号 CI 跑:
- `scripts/verify_spec.py` (M2 校验脚本)
- 三方一致: `app.py` endpoint 数 == `auto-inventory.json` endpoint 数 == `system-functional-spec.md` 章节数
- 不一致 → 邮件 + 阻塞下次 release tag

---

## 关键不变量（汇总）

- M1 baseline 修零: 不删实现, 不引入新依赖
- M2 文档: 数据驱动, 25 核心 endpoint 强 Manual Notes
- M3 测试: 每 endpoint ≥ 4 维度, coverage ≥ 90%
- pre-commit: 物理门, `hotfix` 是唯一豁免关键词
- agent-CR: 6 维, 问题自动喂回优化
- 端点变更: 文档 / 测试 / review 三同步

---

## 实施顺序（提案 A 三阶段）

| 阶段 | 产出 | 工作量估 |
|------|------|---------|
| M1 测试基线修零 | 22 failed + 15 errors → 0 | 1-2 天 |
| M2 系统功能说明文档 | docs/system-functional-spec.md + 3 个脚本 + 25 段 Manual Notes | 2-3 天 |
| M3 测试用例 + pre-commit + agent-CR | tests/functional/ + .pre-commit-config.yaml + .claude/hooks/post-commit | 3-4 天 |

三阶段都可在 main 上独立 commit（用户已确认偏好）。

---

## Open Questions

- OQ1: OpenSpec 现有 7 个 spec 跟 system-functional-spec.md 怎么去重?（建议: spec.md 留架构/能力描述, system-functional-spec.md 留 API 字段级, 不重叠）
- OQ2: agent-CR 的 token 成本估算: 6 维 × diff 长度, 一次 review 大约 5-15k tokens, 接受吗?
- OQ3: pre-commit 跑 audit_test_failures.py 还是只跑 check_tdd_compliance.sh?（建议: pre-commit 只跑后者, audit 在 CI 跑, 因为 audit 慢）
