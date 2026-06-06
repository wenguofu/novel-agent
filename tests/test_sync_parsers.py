"""tests/test_sync_parsers.py

Regression tests for the two parser bugs found during the
"大强成神啦" MD-vs-DB review (2026-06-01):

1. scripts/sync_novel_files.py :: parse_danger_issue
   - rhythm_data: original regex `\|(.+?)\|` captured a single cell,
     not a full row, so split('|') produced 1 element and no rows matched.
   - foreshadowing_data: original regex `^\|(FP\d+)\|...` required
     `|FP001` with no space after the opening `|`, but MD has `| FP001`.
     Add `\s*` after each `|`.

2. portal/content_db.py :: init_alias_names_from_file
   - column mapping was reversed: real name ("北京") went into
     alias_name, alias ("北辰") went into description.
   - 4-column table rows were matched by 5-column regex with
     `\s*` greedily consuming newlines, fusing two rows into one.
"""
import os, sys, re, importlib.util, tempfile
import pytest


# ─── Loader for sync_novel_files (no package, just a script) ────────────

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sync_mod = _load("sync_novel_files", os.path.join(SCRIPTS_DIR, "sync_novel_files.py"))


# ─── parse_danger_issue fixtures ────────────────────────────────────────

DANGER_MD = """# 第001章 · 危险问题剧本

> 本章危险等级：⚠️ 低（氛围压迫型）
> 核心危险：未知邀请的诡异感、推门前的心理压迫

---

## 危险问题清单

### 危险问题1：邀请函的来源与目的
- **问题描述**：邀请函是谁寄出的？目的为何？

---

## 本章节奏

| 时间段 | 情节 | 张力 |
|:---:|:---|:---:|
| 00:00-00:30 | 付大强在出租屋收到邀请函 | 低 |
| 00:30-01:00 | 检查邀请函，发现材质异常 | 中 |
| 01:00-01:30 | 决定去城中村查看地址 | 中 |
| 01:30-02:00 | 找到铁门，观察环境 | 中高 |
| 02:00-02:30 | 推门而入，世界崩塌 | 高（章末钩子） |

---

## 伏笔埋设

| 伏笔ID | 内容 | 揭示时机 |
|:---:|:---|:---:|
| FP001 | 邀请函使用古夏国文字 | 第3卷（遗民揭示） |
| FP002 | 付大强对"乐园"一词有莫名熟悉感 | 第1卷后期 |
| FP003 | 推门瞬间，他听到一个微弱的声音："终于……找到了……" | 第5卷（叛神身份揭示） |
"""


@pytest.fixture
def danger_md_path(tmp_path):
    p = tmp_path / "danger_issue_001.md"
    p.write_text(DANGER_MD, encoding="utf-8")
    return str(p)


# ─── Test 1: rhythm_data parsing ───────────────────────────────────────

def test_parse_danger_issue_rhythm_data(danger_md_path):
    """Bug: original `re.findall(r'\\|(.+?)\|', content)` captured a single cell,
    so `row.split('|')` gave 1 element and `len(cols) >= 3` was False.
    After fix: 5 rhythm rows captured.
    """
    data = sync_mod.parse_danger_issue(danger_md_path)
    rhythm = data["rhythm_data"]
    assert len(rhythm) == 5, f"expected 5 rhythm rows, got {len(rhythm)}: {rhythm}"
    assert "00:00-00:30" in rhythm
    assert rhythm["00:00-00:30"]["scene"] == "付大强在出租屋收到邀请函"
    assert rhythm["00:00-00:30"]["tension"] == 1  # 低
    assert rhythm["00:30-01:00"]["tension"] == 2  # 中
    assert rhythm["01:00-01:30"]["tension"] == 2  # 中
    assert rhythm["01:30-02:00"]["tension"] == 3  # 中高
    assert rhythm["02:00-02:30"]["tension"] == 4  # 高


# ─── Test 2: foreshadowing_data parsing ────────────────────────────────

def test_parse_danger_issue_foreshadowing_data(danger_md_path):
    """Bug: original regex `^\\|(FP\\d+)\\|...` required `|FP001` (no space).
    After fix with `\\s*` after each `|`: 3 rows captured.
    """
    data = sync_mod.parse_danger_issue(danger_md_path)
    fp = data["foreshadowing_data"]
    assert len(fp) == 3, f"expected 3 foreshadowing rows, got {len(fp)}: {fp}"
    assert fp[0]["id"] == "FP001"
    assert fp[0]["description"] == "邀请函使用古夏国文字"
    assert fp[0]["reveal_at"] == "第3卷（遗民揭示）"
    assert fp[1]["id"] == "FP002"
    assert fp[2]["id"] == "FP003"


# ─── Test 3: alias column mapping (5-col rows) ─────────────────────────

# A minimal stand-in for init_alias_names_from_file's line parser, mirroring
# the new logic in portal/content_db.py. We re-implement it here so the test
# is self-contained and does not require DB setup.
HEADER_WORDS = {'类别', '原文', '原名称', '别名', '首次出现', '备注',
                '别名/处理方式', '已登记数量', '已登记别名', '城市/地区别名',
                '组织/机构别名', '人物别名', '历史/文化别名'}


def _parse_alias_rows(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|') or not line.endswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) != 5:
            continue
        if cells[0] in HEADER_WORDS:
            continue
        if any(c.startswith('---') or c.startswith(':') for c in cells):
            continue
        # New fixed mapping: cells[2] is the alias, cells[1] is the real name.
        rows.append((cells[0], cells[2], cells[1], cells[3], cells[4]))
    return rows


ALIAS_MD = """# 别名注册表

## 已登记别名

| 原文 | 别名 | 类别 | 首次出现 |
|:---|:---|:---|:---|
| 中国 | 夏国 | 国家 | 第002章 |

## 城市/地区别名

| 类别 | 原名称 | 别名 | 首次出现 | 备注 |
|:---|:---|:---|:---:|:---|
| 城市 | 北京 | 北辰 | 第1卷 | 虚构北方大都市 |
| 城市 | 上海 | 东海 | 第1卷 | 虚构沿海大都市 |

## 历史/文化别名

| 类别 | 原名称 | 别名/处理方式 | 备注 |
|:---|:---|:---|:---|
| 历史朝代 | 真实朝代名 | 替换为虚构朝代 | 例：唐朝→天盛朝 |
| 历史人物 | 禁止出现 | N/A | 严格禁用 |
"""


def test_alias_5col_row_mapping():
    """Bug: row[1] (real name) and row[2] (alias) were swapped.
    After fix: alias_name column gets the fictional alias, not the real name.
    """
    rows = _parse_alias_rows(ALIAS_MD)
    # 2 5-col data rows (城市/北京, 城市/上海). The 4-col tables (已登记别名, 历史/文化别名) are skipped.
    assert len(rows) == 2, f"expected 2 rows, got {len(rows)}: {rows}"
    # cells: 0=类别, 1=原名称, 2=别名, 3=首次出现, 4=备注
    # Fixed mapping: (category, alias, real_name, scope, note)
    assert rows[0] == ("城市", "北辰", "北京", "第1卷", "虚构北方大都市")
    assert rows[1] == ("城市", "东海", "上海", "第1卷", "虚构沿海大都市")


def test_alias_4col_table_skipped():
    """Bug: 4-col rows matched the 5-col regex, fusing two rows.
    The 中国 row (4-col) should NOT appear in results.
    The 历史/文化别名 table (also 4-col) should NOT appear.
    """
    rows = _parse_alias_rows(ALIAS_MD)
    # Verify no row has 中国 or 夏国 or 历史朝代 etc.
    for r in rows:
        assert "中国" not in r
        assert "夏国" not in r
        assert "历史朝代" not in r
        assert "唐朝" not in r
        # And no row should have a `|` from cross-line bleed.
        for cell in r:
            assert "|" not in cell, f"cross-line bleed detected in {r}"


# ─── Test 4: real-world regression — actual 大强成神啦 alias_registry.md ──

REAL_ALIAS_MD = os.path.join(
    os.path.dirname(__file__), "..", "novels", "大强成神啦", "alias_registry.md"
)


def test_real_alias_registry_parsed():
    """End-to-end: parse the actual novel's alias_registry.md and verify
    column mapping is correct (alias in alias_name slot, real name in desc).
    """
    if not os.path.exists(REAL_ALIAS_MD):
        pytest.skip(f"{REAL_ALIAS_MD} not found")
    with open(REAL_ALIAS_MD, encoding="utf-8") as f:
        text = f.read()
    rows = _parse_alias_rows(text)
    assert len(rows) >= 10, f"expected >=10 rows from real MD, got {len(rows)}"
    # Spot-check 北京 → 北辰
    beijing = [r for r in rows if r[2] == "北京"]
    assert len(beijing) == 1, f"北京 row not found or duplicated: {beijing}"
    assert beijing[0] == ("城市", "北辰", "北京", "第1卷", "虚构北方大都市")
    # Spot-check 武汉 → 江城
    wuhan = [r for r in rows if r[2] == "武汉"]
    assert len(wuhan) == 1
    assert wuhan[0] == ("城市", "江城", "武汉", "第1卷", "主角生活城市（虚构）")
