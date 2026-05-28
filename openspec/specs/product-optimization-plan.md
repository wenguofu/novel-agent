# Novel Agent v3 深度产品审查与优化计划

> 审查日期: 2026-05-26 | 审查范围: 全部6层 | 方法: 逐行代码审计 + 运行时验证

---

## 审查方法

逐层审计: API层(2125行) → 数据层(1177行+3模块) → 前端层(2663行JS) → 脚本层(11脚本2504行) → Agent层(12团队定义+4工作流) → 运行时(Portal实际页面)

---

## 一、发现的缺陷 (按严重度)

### 🔴 P0 — 线上Bug/功能阻断

#### BUG-01: 质量报告SQL字段错配 (静默失败)
- **位置**: `app.py:1538-1541` — 查询 `wc_ok, compliance_ok, forbidden_ok, bcontrast_count, tell_count, judgment_groups`
- **schema**: `reviews` 表实际字段是 `script_analyze_ok, script_compliance_ok, script_forbidden_ok`，无 `bcontrast_count` 等列
- **影响**: 质量报告页面永远返回0/空，用户看到的统计全是假数据
- **修复**: 对齐字段名，或先 ALTER TABLE 加列再改查询

#### BUG-02: 审稿INSERT字段错配 (静默失败)
- **位置**: `app.py:905-913` — INSERT写入 `wc_ok, compliance_ok, forbidden_ok, bcontrast_count, judgment_groups, tell_count`
- **包裹**: `try/except Exception: pass` — 字段不存在的SQL错误被静默吞掉
- **影响**: 每次审稿后review记录写入失败，但用户不知情。质量报告完全无数据
- **修复**: 先在 `content_db.py` 的 SCHEMA 和 migrate_v3 中添加 `wc_ok/bcontrast_count/tell_count/judgment_groups` 扩展列

#### BUG-03: 双轨上下文系统 — generate-chapter不使用v3引擎
- **位置**: `app.py:699-817` (`api_generate_chapter`) 自行构建prompt，直接加载8个文件+硬截断
- **对比**: v3 context builder有9层按需加载+向量检索+token预算+节奏/释放约束
- **影响**: 
  - 非流式生成（批量续写、重写触发）完全跳过v3智能上下文，退化为v2的粗暴全量加载
  - 流式生成走JS→`/api/context/build`（正确），非流式走旧逻辑
  - 同一系统两种上下文质量，用户不可感知
- **修复**: `api_generate_chapter` 改为调用 `context_builder.build_context()` 获取system_prompt

#### BUG-04: Context Builder截断算法错误
- **位置**: `context_builder.py:91` — `content[:allocated * 2]`
- **问题**: `allocated` 是token数，不是字符数。中文1字符≈1.5 token，`[:allocated * 2]` 截断量远小于预期
- **影响**: 上下文实际token可能远超预算（字符截断不够），token预算形同虚设
- **修复**: 改为逐段添加+token计数，到达预算即停止

#### BUG-05: Portal初始化时JS异常
- **观察**: 浏览器访问Portal → 控制台报告1个JS异常，主内容区空白
- **影响**: 用户首次访问可能看到空白页，需刷新
- **修复**: 排查JS初始化顺序，添加error boundary

#### BUG-06: 审稿数据静默丢失
- **位置**: `app.py:917-918` — 插入reviews失败后 `except Exception: pass`
- **外加**: BUG-02导致INSERT必然失败
- **影响**: 审稿脚本实际跑了，但结构化数据从未存入DB，只写了markdown文件
- **修复**: 关联BUG-02修复后自然解决

---

### 🟡 P1 — 架构/设计缺陷

#### ARCH-01: 无Token使用追踪
- `usage.db` 已创建但从未写入。`deepseek_chat()` 和 SSE流都不记录token消耗
- **影响**: 用户完全不知道花了多少钱、哪个小说最费token、哪个操作最烧钱
- **方案**: 在 `deepseek_chat()` 成功返回后写 usage 表；SSE流在 `done` 事件时写入

#### ARCH-02: 错误吞噬模式泛滥
- 统计 `app.py` 中 `try/except Exception: pass` 模式: 至少6处
- 包括: sync_novel_from_files失败、auto_update失败、review INSERT失败、RAG更新失败
- **影响**: 关键数据写入失败时用户毫无感知，数据不一致积累
- **方案**: 最低要求 `logging.exception()` 记录，理想状态前端toast通知

#### ARCH-03: 脚本Python环境不可靠
- `run_script()` 使用 `sys.executable` 但 Portal 运行在hermes venv，脚本依赖 `chromadb/sentence-transformers` 不在该venv中
- **影响**: RAG相关脚本(`rag_query.py/rag_index.py`)可能因缺少依赖而失败
- **方案**: 检查venv中是否安装这些包，未安装则自动pip install

#### ARCH-04: init_engine.py模块缺失
- 功能已实现在 `content_db.py` 中(init_world_building_from_file等)，但独立模块规划未落实
- `content_db.py` 达1177行，职责混杂(CRUD+初始化+解析)
- **方案**: 按Phase 2设计独立化，降低耦合

#### ARCH-05: 双轨Prompt质量问题
- 流式生成: JS调用 `/api/context/build` → 9层按需上下文 ✅
- 非流式生成: `api_generate_chapter` 加载8文件×3000字符 ❌ (无向量检索，无节奏约束)
- 重写: `_rewriteChapter` 调用 `_buildSystemPrompt` → `/api/context/build` ✅ (但紧接着又叠加了review文本，可能超token)
- **影响**: 不同操作上下文质量不一致，用户困惑
- **方案**: 所有生成入口统一走 `/api/context/build`

#### ARCH-06: 前端文件过大
- `app.js` 2663行单文件，包含所有页面渲染+业务逻辑+流处理+样式
- 无模块化，所有函数挂在 `App` 对象上，命名空间污染风险高
- **方案**: 按页面拆分为 `writing.js/chapters.js/review.js/quality.js/characters.js` 等模块

---

### 🟢 P2 — 功能缺失/体验缺陷

#### FEAT-01: v3管理页面完全缺失
- world_building / plot_arcs / pacing_control / revelation_schedule 四张表有后端CRUD无前端UI
- **影响**: 用户无法查看/编辑这些v3核心数据，AI上下文质量完全依赖init解析质量
- **优先级**: MAX — 这是当前最大的功能缺口

#### FEAT-02: 无版本对比/Diff
- `.bak` 目录存储了历史版本，但无UI查看
- **影响**: 优化后不知道改了哪里，只能信任AI

#### FEAT-03: 无导出功能
- 所有内容以markdown存储，无法导出为epub/txt/html
- **影响**: 写完的小说无法交付

#### FEAT-04: 生成前约束未注入
- pacing_control和revelation_schedule表存了节奏/情感/信息释放约束
- 但在生成章节时这些约束没有被注入system prompt
- context_builder.py的Layer 6和Layer 7只在build_context时组装，但generate-chapter没用build_context
- **影响**: v3的节奏控制功能形同虚设

#### FEAT-05: 质量管理页面数据为空
- 因BUG-01，质量报告所有指标为0，页面几乎无价值
- 即使修复，目前的指标维度也偏少(仅字数/合规/禁用模式)

#### FEAT-06: 无跨卷人物状态快照
- 角色current_status在DB中更新，但卷切换时无自动快照
- vol-01结束时的状态 → vol-02开始时的状态需要人工确认

#### FEAT-07: 无章节间情感/节奏曲线可视化
- pacing_control表有intensity(1-10)和emotion_target
- 但没有前端可视化展示，用户看不到"情感曲线"

#### FEAT-08: 写作速度/产能统计缺失
- 无"今天写了多少字""本周产能""单章平均耗时"等基础统计
- 作者对自身产能无感知

#### FEAT-09: 配置页面对比缺失
- 用户调整temperature/max_tokens/model后无法对比不同配置的生成效果
- 无A/B测试机制

#### FEAT-10: 批量操作能力弱
- 无法批量审稿、批量重写、批量导出
- 每章都需要手动操作

---

## 二、逐模块现状评估与优化建议

### 模块1: API层 (app.py, 2125行)

| 端点类别 | 数量 | 评估 | 问题 |
|----------|------|------|------|
| Novels CRUD | 6 | ✅ 完整 | 无 |
| Chapters | 3 | ✅ 完整 | 编辑后auto_update正常 |
| Reviews | 1 | ⚠️ 写入失败 | BUG-02字段不匹配 |
| AI Chat/Stream | 2 | ✅ 可用 | Stream路径正确，Chat路径不用v3 |
| Generate | 1 | ❌ 严重 | 用旧版上下文，不用v3 |
| Workflow | 3 | ✅ 可用 | 脚本路径正确 |
| Config | 4 | ✅ 完整 | 保存合并逻辑正确 |
| Wizard | 1 | ✅ 可用 | 8步向导完整 |
| Context(v3) | 2 | ⚠️ 有bug | BUG-04截断错 |
| RAG(v3) | 1 | ⚠️ 未用 | endpoint存在但无人调用 |
| Init(v3) | 1 | ✅ 完整 | 6表初始化正常 |
| Characters | 5 | ✅ 完整 | CRUD+事件+init |
| Foreshadowing | 4 | ✅ 完整 | CRUD+unresolved+init |
| Quality | 1 | ❌ 损坏 | BUG-01字段错配 |
| Config-DB | 3 | ✅ 完整 | 4表CRUD |

**优化项**:
1. 统一所有生成入口走 `context_builder.build_context()` (消除双轨)
2. 添加 token 使用记录 (usage.db写入)
3. 添加 `/api/export/<format>` 端点
4. 添加 `/api/compare/<ch_ref>` diff端点
5. 添加 `/api/stats/writing-speed` 产能统计端点
6. 错误处理: 替换 `except Exception: pass` 为 `logging.exception()` + 返回warning

### 模块2: 数据层 (content_db.py 1177行 + context_builder + rag_engine + token_budget)

| 组件 | 行数 | 评估 | 问题 |
|------|------|------|------|
| content_db.py | 1177 | ⚠️ 过大 | 职责混杂，需拆分 |
| context_builder.py | 409 | ⚠️ 有bug | BUG-04截断+不读rag |
| rag_engine.py | 169 | ✅ 可用 | chroma回退正常 |
| token_budget.py | 32 | ⚠️ 太简单 | 无优先级分配，剩余token全给最后一层 |

**优化项**:
1. **content_db.py拆分**:
   ```
   portal/
   ├── content_db.py       # 核心CRUD (精简到~600行)
   ├── init_engine.py      # 所有init_*函数 (从现在content_db.py后半搬出)
   ├── context_builder.py  # 修复截断+集成rag_engine
   └── rag_engine.py       # 保持
   ```

2. **token_budget.py增强**: 支持优先级分配、硬/软预算、类别最小保证量
   当前: `allocate(category, requested)` → `min(requested, remaining)` 简单线性
   期望: `allocate(category, requested, priority=5, min_guaranteed=100)` 智能分配

3. **context_builder.py重构**:
   - 修复截断: 改为字符→token实时计数
   - 集成RAG: Layer 3(角色)和Layer 5(世界观)当前是DB查询，应改为vector检索
   - 动态截断: 当token不足时，按优先级裁剪而不是简单截断

4. **reviews表schema扩展** (修复BUG-01+BUG-02):
   ```sql
   ALTER TABLE reviews ADD COLUMN wc_ok INTEGER DEFAULT 0;
   ALTER TABLE reviews ADD COLUMN compliance_ok INTEGER DEFAULT 0;
   ALTER TABLE reviews ADD COLUMN forbidden_ok INTEGER DEFAULT 0;
   ALTER TABLE reviews ADD COLUMN bcontrast_count INTEGER DEFAULT 0;
   ALTER TABLE reviews ADD COLUMN tell_count INTEGER DEFAULT 0;
   ALTER TABLE reviews ADD COLUMN judgment_groups INTEGER DEFAULT 0;
   ```
   或简化: 直接查询已有的 `script_analyze_ok/script_compliance_ok/script_forbidden_ok` 替代

### 模块3: 前端层 (app.js 2663行 + index.html + api.js)

| 页面 | 渲染函数 | 评估 |
|------|----------|------|
| 控制台 | _renderDashboard | ⚠️ 基本可用 |
| 项目 | _renderNovels | ✅ 可用 |
| 创建新书 | _renderNewBook | ✅ 8步向导 |
| 写作台 | _renderWriting | ✅ 流式+自动审稿 |
| 章节浏览 | _renderChapters | ✅ 搜索+筛选 |
| 审稿 | _renderReview | ✅ 双阶段进度 |
| 初始化向导 | _renderInitWizard | ✅ 可用 |
| 人物管理 | _renderCharacters | ✅ 完整 |
| 伏笔管理 | _renderForeshadowing | ✅ 完整 |
| 工作流检查 | _renderWorkflow | ✅ 可用 |
| 大纲管理 | _renderOutlines | ⚠️ tab切换有DOM销毁问题 |
| 质量报告 | _renderQuality | ❌ 数据为0(BUG-01) |
| 全文搜索 | _renderSearch | ✅ 可用 |
| 配置管理 | _renderConfig | ✅ 可用 |
| 设置 | _renderSettings | ✅ 可用 |
| **世界观管理** | **缺失** | ❌ |
| **剧情弧线** | **缺失** | ❌ |
| **节奏控制** | **缺失** | ❌ |
| **信息释放** | **缺失** | ❌ |

**优化项**:
1. **拆分app.js**: 按页面模块化 (12-15个js文件)
   ```
   static/js/
   ├── app.js           # 路由+全局状态 (~200行)
   ├── pages/
   │   ├── dashboard.js
   │   ├── writing.js
   │   ├── review.js
   │   ├── characters.js
   │   ├── foreshadowing.js
   │   ├── workflow.js
   │   ├── quality.js
   │   ├── world-building.js   (新增)
   │   ├── plot-arcs.js        (新增)
   │   ├── pacing-control.js   (新增)
   │   └── revelation.js       (新增)
   ├── api.js           # 保持
   └── utils.js         # markdown渲染等
   ```

2. **新增4个v3管理页面**: (最高优先级)
   - 世界观管理: domain分组卡片+全文搜索+内联编辑
   - 剧情弧线: 时间线视图+milestones可视化
   - 节奏控制: 热力图(intensity×pace_type色块)+拖拽调整
   - 信息释放: 时间线视图+双轨(audience/protagonist)

3. **质量报告增强**:
   - 修复数据源(BUG-01)
   - 增加: 情感曲线图、伏笔密度分布、人物出场频率、写作速度趋势
   - 增加: 章节间对比(字数变化率、节奏类型分布)

4. **交互增强**:
   - 键盘快捷键: Ctrl+Enter生成, Ctrl+S保存, Ctrl+Shift+R审稿
   - 深色模式在index.html中CSS变量完整覆盖
   - Toast通知系统统一化(当前分散在多个页面中)

### 模块4: 脚本强制层 (agent-system/scripts/, 11脚本2504行)

| 脚本 | 行数 | 调用方式 | 评估 |
|------|------|----------|------|
| stage_gate.py | 196 | Portal run_script | ✅ 7阶段状态机 |
| agent_tracker.py | 243 | enforce-pipeline | ✅ Agent存在性检查 |
| analyze_chapter.py | 265 | review-chapter | ✅ 字数/结构分析 |
| check_compliance.py | 274 | review-chapter | ✅ 130+禁用词 |
| detect_forbidden_patterns.py | 301 | review-chapter | ✅ 文笔反模式 |
| validate_review.py | 127 | enforce-pipeline | ✅ 审稿格式校验 |
| verify_continuity.py | 92 | enforce-pipeline | ⚠️ 新建,未充分测试 |
| rhythm_check.py | 259 | enforce-pipeline | ✅ 5节奏规则 |
| rag_index.py | 292 | enforce-pipeline+手动 | ⚠️ chromadb依赖 |
| rag_query.py | 340 | enforce-pipeline+手动 | ⚠️ chromadb依赖 |
| rag_context.py | 115 | 未在Portal中使用 | ⚠️ 被context_builder替代? |

**优化项**:
1. **脚本环境标准化**: 所有脚本统一使用 `content_db.py` 中的RAG接口，不再各自连接chromadb
2. **rag_context.py废弃或合并**: 其功能已被 `context_builder.py` 覆盖，但 `context_builder` 没用RAG(这是BUG)
3. **analyze_chapter.py输出格式标准化**: 当前stdout格式依赖正则解析(`bcontrast_count: X`)，应改为JSON输出
4. **check_compliance.py配置化**: banned_words应从 `config.db` 动态读取而非硬编码
5. **verify_continuity.py补测试**: 92行仅基于正则匹配，可能需要更智能的连续性检测

### 模块5: Agent定义层 (agent-system/, 12团队+4工作流)

| 文件 | 评估 |
|------|------|
| system-prompt.md (73行) | ⚠️ 被Portal内联prompt覆盖，未同步更新 |
| team.md (57行) | ⚠️ Agent定义在Portal中未直接使用 |
| team/*.md (12个Agent) | ⚠️ 仅作为参考文档，未被Portal引用 |
| writer-style-skill.md (548行) | ⚠️ 大量风格定义，仅前端STYLE_OPTIONS使用 |
| compliance.md | ✅ 合规规则被check_compliance.py使用 |
| workflows/*.md (5个工作流) | ⚠️ 作为参考文档，enforce-pipeline是其脚本化实现 |

**优化项**:
1. **system-prompt.md 统一**: Portal内联和文件中的prompt应同步，避免system-prompt.md过时
2. **Agent定义活化**: team/*.md中的Agent角色定义可注入context builder的Layer 0(核心指令)
3. **工作流脚本化**: 所有 `workflows/*.md` 中的步骤都应有对应的脚本/API端点

### 模块6: 总体系统架构

**当前架构**:
```
┌────────────┐  ┌─────────────┐  ┌──────────────┐
│  app.js    │→│  /api/ai/   │→│  DeepSeek API │
│  (前端)     │  │  stream     │  │              │
│            │  │  (SSE)      │  └──────────────┘
│ ┌────────┐ │  └─────────────┘
│ │_build  │ │  ┌─────────────┐
│ │System  │→│→│ /api/context │ ← v3路径 ✅
│ │Prompt  │ │  │ /build       │
│ └────────┘ │  └─────────────┘
│            │  ┌─────────────┐
│ _gen      │→│  /api/generate│ ← 旧路径 ❌
│ Chapter   │  │ -chapter     │    (不用v3)
└────────────┘  └─────────────┘
```

**期望架构**:
```
┌────────────┐  ┌──────────────┐  ┌──────────────┐
│  所有前端   │→│ /api/context  │→│  DeepSeek API │
│  生成入口   │  │ /build (统一) │  │              │
│            │  │              │  │              │
└────────────┘  │ ┌──────────┐ │  └──────────────┘
                │ │ DB查询    │ │
                │ │ Vector检索│ │
                │ │ Token预算 │ │
                │ └──────────┘ │
                └──────────────┘
```

---

## 三、系统级优化路线图

### Sprint 1: 止血 (1-2天) — P0 Bug修复

```
□ Fix BUG-01: 质量报告字段对齐
  → 方案A(快): 查询改为用 reviews 表已有字段 (script_analyze_ok/compliance_ok/forbidden_ok)
  → 方案B(完整): ALTER TABLE 加6列 → 修INSERT → 修查询
  
□ Fix BUG-02: 审稿INSERT字段匹配
  → 跟随BUG-01方案，统一字段名

□ Fix BUG-03: generate-chapter 改用 v3 context builder
  → api_generate_chapter() 中，将 ~90行内联prompt构建替换为:
    from context_builder import build_context
    ctx = build_context({name, volume, chapter_num, style, instructions, max_tokens})
    system_prompt = ctx['system_prompt']

□ Fix BUG-04: context_builder 截断算法
  → 将 content[:allocated * 2] 改为逐段添加+_count_tokens实时检查

□ Fix BUG-05: Portal JS初始化异常
  → 排查console错误，添加初始化error boundary
```

### Sprint 2: 对齐 (3-4天) — 前端补齐+上下文统一

```
□ [核心] 新增4个v3管理页面
  → 世界观管理 (world_building CRUD UI)
  → 剧情弧线管理 (plot_arcs 时间线视图)
  → 节奏控制台 (pacing_control 热力图)
  → 信息释放管理 (revelation_schedule 时间线)

□ 统一上下文入口
  → review-chapter 也改用 context_builder (当前只传genre+chars)
  → optimize-chapter 注入当前章节的pacing/revelation约束
  → 删除 api_generate_chapter 中的旧prompt构建代码

□ token_budget 增强
  → 支持优先级: characters(高) > world_building(高) > plot_arcs(中) > style(低)
  → 支持最小保证量: 每层至少100 token

□ context_builder 集成RAG
  → Layer 3(角色)改为: DB获取角色列表 → RAG搜索当前章节相关
  → Layer 5(世界观)改为: DB获取domain → RAG搜索卷相关
```

### Sprint 3: 加固 (3-5天) — 质量+稳定性

```
□ Token追踪落地
  → deepseek_chat() 每次调用后写入 usage.db
  → SSE done 事件写入 usage.db
  → 新增 /api/usage/stats 端点
  → 前端增加 📊 Token用量 页面 (按小说/操作/时间维度)

□ 错误处理规范化
  → 替换所有 except Exception: pass 为 logging.exception()
  → 关键操作失败时返回 warning 到前端
  → 新增 /api/system/health 健康检查端点 (检查DB/chromadb/脚本)

□ 质量报告增强
  → 修复数据源 (Sprint 1)
  → 新增: 情感曲线 (基于chapters.emotional_beat)
  → 新增: 伏笔密度 (每章foreshadowing_touched数量)
  → 新增: 节奏分布 (pace_type统计)

□ 脚本输出标准化
  → analyze_chapter.py → JSON输出
  → 所有脚本统一 stderr=warnings, stdout=results
  → Portal解析不再依赖正则

□ 前端模块化
  → 拆分 app.js 为12-15个模块文件
  → 用 ES modules 或 IIFE 命名空间隔离
```

### Sprint 4: 扩展 (5-7天) — 新功能

```
□ 版本对比UI
  → /api/compare/<novel>/<ch_ref>/<rev1>/<rev2>
  → 前端: 并排diff视图 (类似GitHub)

□ 导出管线
  → Markdown → EPUB (pandoc或自定义模板)
  → Markdown → TXT (清洗+段落格式化)
  → Markdown → HTML (阅读视图)

□ 批量操作
  → 批量审稿 (选定范围章节一键审稿)
  → 批量重写 (基于最新审稿意见)
  → 批量导出

□ 情感/节奏曲线可视化
  → 基于 chapters.emotional_beat 和 pacing_control 表
  → Chart.js或Canvas绘制曲线图

□ 产能Dashboard
  → 字数/天趋势
  → 单章平均耗时
  → 目标进度(如果设置了word_goal)
```

### Sprint 5: 高级 (7-10天) — 差异化竞争力

```
□ 多卷协同编排
  → 卷间人物状态快照自动保存
  → 跨卷伏笔依赖图可视化
  → "开卷检查清单" 自动化

□ A/B生成对比
  → 同章用不同temperature生成2-3版本
  → 并排对比+投票

□ 写作分析引擎
  → 人物出场频率热力图
  → 章节功能标签分布 (高潮章/铺垫章/过渡章)
  → 伏笔填坑率统计

□ 智能建议
  → "连续3章低于2000字→建议调整节奏" (已有)
  → "某人物10章未出场→提醒回归" (新增)
  → "当前卷伏笔填坑率仅30%→需要加快" (新增)

□ 模板系统
  → 存为模板: genre_bible + world_bible + characters
  → 从模板创建: 跨小说复用世界观
```

---

## 四、技术债务清单

| 项目 | 严重度 | 说明 | 预计工时 |
|------|--------|------|----------|
| content_db.py 拆分为2-3文件 | 中 | init函数独立到init_engine.py | 2h |
| app.js 模块化拆分 | 高 | 2663行单文件难维护 | 4h |
| try/except:pass 替换 | 高 | 6+处静默吞错误 | 1h |
| generate-chapter 旧代码清理 | 高 | 删除旧prompt构建，统一用context_builder | 1h |
| venv依赖检查 | 中 | chromadb/sentence-transformers | 1h |
| 前端样式一致性 | 低 | CSS变量未完全覆盖深色模式 | 2h |
| agent-system目录整理 | 低 | scripts/与team/与根文件混放 | 1h |
| 测试覆盖率 | 中 | 当前47个测试仅覆盖DB层，缺API/前端测试 | 8h |

---

## 五、优先级执行矩阵

```
            高影响                          低影响
高紧急  ┌─────────────────────────┬──────────────────────────┐
        │ Sprint 1 (1-2天)        │ Sprint 1 (续)             │
        │ BUG-01 质量报告字段修复   │ BUG-05 JS初始化异常       │
        │ BUG-02 审稿INSERT修复    │ BUG-06 审稿数据静默丢失    │
        │ BUG-03 上下文统一        │                          │
        │ BUG-04 截断算法修复      │                          │
        ├─────────────────────────┼──────────────────────────┤
        │ Sprint 2 (3-4天)        │ Sprint 3 (续)             │
        │ 4个v3管理页面            │ 脚本输出JSON标准化         │
        │ 上下文入口统一           │ 前端模块化                │
        │ token_budget增强        │                          │
        ├─────────────────────────┼──────────────────────────┤
        │ Sprint 3 (3-5天)        │ Sprint 5 (7-10天)         │
        │ Token追踪落地            │ 多卷协同                  │
        │ 错误处理规范化           │ A/B对比                  │
        │ 质量报告增强             │ 模板系统                 │
低紧急  ├─────────────────────────┼──────────────────────────┤
        │ Sprint 4 (5-7天)        │ 持续改进                  │
        │ 版本对比UI               │ 测试覆盖率提升             │
        │ 导出管线                 │ 样式一致性                │
        │ 批量操作                 │ 代码文档                  │
        │ 产能Dashboard            │                          │
        └─────────────────────────┴──────────────────────────┘
```

---

## 六、关键指标 (优化后目标)

| 指标 | 当前值 | 目标值 | 
|------|--------|--------|
| 质量报告数据可用性 | 0% (全部为0) | 100% |
| 上下文统一度 | 50% (双轨) | 100% (单一入口) |
| Token追踪覆盖 | 0% | 100% (每次API调用) |
| v3功能前端覆盖 | 60% (4/8模块缺UI) | 100% |
| 错误可见性 | 0% (静默吞掉) | 90% (logging+toast) |
| 前端文件数 | 3 (app.js+api.js+index.html) | 15+ (模块化) |
| 测试覆盖 | DB层47个 | DB+API+前端 80+ |
| 生成上下文质量 | 参差不齐 (双轨) | 一致 (v3 context builder) |
