"""
Phase 2: Init Engine Tests — RED phase
Tests that init_from_files correctly populates domain tables.
Uses a mock novel directory with sample files.
"""

import json
import sqlite3
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import content_db as db


@pytest.fixture
def mock_novel(tmp_path):
    """Create a mock novel directory with sample files for testing init"""
    novel_dir = tmp_path / "novels" / "test_novel"
    manuscript_dir = novel_dir / "manuscript" / "vol-01"
    outline_dir = novel_dir / "outline"
    state_dir = novel_dir / "state"

    for d in [manuscript_dir, outline_dir, state_dir]:
        d.mkdir(parents=True)

    # project.md
    (novel_dir / "project.md").write_text("""# Test Novel

## 作品信息
| 字段 | 内容 |
|:---|:---|
| 标题 | 测试小说 |
| 类型 | 玄幻 · 修仙 |
| 目标篇幅 | 100 万字 |

## 世界观核心
- 灵气体系：天地灵气分为金木水火土五系
- 修炼等级：练气→筑基→金丹→元婴→化神
- 禁地：死亡沼泽，入者必死
""", encoding='utf-8')

    # world_bible.md
    (novel_dir / "world_bible.md").write_text("""# 世界观设定

## 力量体系
- 灵气等级：练气(1-9层)→筑基→金丹→元婴→化神
- 每个大境界分初期、中期、后期、圆满
- 突破需要丹药辅助

## 地图
- 东荒：主角出生地，资源贫瘠
- 中州：修炼圣地，宗门林立
- 死亡沼泽：禁地，入者必死

## 规则
- 天道法则：因果循环，杀戮过多必有天劫
- 宗门铁律：背叛师门者，废去修为
""", encoding='utf-8')

    # characters.md
    (novel_dir / "characters.md").write_text("""# 人物档案

## 主角
### 陈凡
| 字段 | 内容 |
|:---|:---|
| 姓名 | 陈凡 |
| 身份 | 青云宗外门弟子 |
| 异能 | 五行灵根 |

## 女主
### 苏灵儿
| 字段 | 内容 |
|:---|:---|
| 姓名 | 苏灵儿 |
| 身份 | 天剑宗圣女 |

## 主要配角
### 青云宗主
| 字段 | 内容 |
|:---|:---|
| 身份 | 青云宗掌门 |
""", encoding='utf-8')

    # full_story_arc.md
    (novel_dir / "full_story_arc.md").write_text("""# 主线剧情

## 第一卷：青云崛起
陈凡从外门弟子开始，在宗门大比中脱颖而出。

## 第二卷：中州风云
陈凡进入中州，参与宗门之战。中途发现自己是上古大能转世。

## 第三卷：天道之争
陈凡对抗天道，最终成仙。
""", encoding='utf-8')

    # outline/vol-01-chapters.md
    (outline_dir / "vol-01-chapters.md").write_text("""# 第一卷章纲

## 第一幕：入门篇 (001-010章)

**第001章 杂役弟子**
- 核心事件：陈凡进入青云宗，被分配为杂役
- 节奏：铺垫，情感目标：压抑
- 伏笔埋设：陈凡的灵根异象

**第002章 意外发现**
- 核心事件：陈凡在后山发现神秘洞穴
- 节奏：过渡→小高潮，情感目标：好奇→惊喜
- 伏笔揭示：洞穴中的古卷暗示上古传承

**第003章 初次修炼**
- 核心事件：陈凡首次引气入体
- 节奏：铺垫，情感目标：期待
- 信息释放：灵气体系基础规则
""", encoding='utf-8')

    # Override NOVELS_ROOT for testing
    old_root = db.NOVELS_ROOT
    db.NOVELS_ROOT = str(tmp_path / "novels")
    yield {
        'novel_name': 'test_novel',
        'novel_dir': str(novel_dir),
        'tmp_path': str(tmp_path),
    }
    db.NOVELS_ROOT = old_root


@pytest.fixture
def fresh_db(mock_novel, tmp_path):
    """Create fresh DB + init the test novel"""
    db_path = tmp_path / "content.db"
    old_db_path = db.DB_PATH
    db.DB_PATH = str(db_path)
    db.init_db()

    # Register novel
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO novels (name, title, genre) VALUES (?, ?, ?)",
                 ('test_novel', '测试小说', '玄幻'))
    conn.commit()
    conn.close()

    yield
    db.DB_PATH = old_db_path


class TestWorldBuildingInit:
    """Test world_building initialization from world_bible.md"""

    def test_wb_init_creates_entries(self, mock_novel, fresh_db):
        """Should create world_building entries from world_bible.md"""
        # This should fail until init is implemented
        from content_db import init_world_building_from_file
        result = init_world_building_from_file('test_novel')
        assert result['created'] > 0, f"Expected >0 entries, got {result}"
        conn = sqlite3.connect(db.DB_PATH)
        rows = conn.execute(
            "SELECT * FROM world_building WHERE novel_id=1").fetchall()
        conn.close()
        assert len(rows) >= 2, f"Expected >=2 world_building rows, got {len(rows)}"

    def test_wb_init_domains(self, mock_novel, fresh_db):
        from content_db import init_world_building_from_file
        init_world_building_from_file('test_novel')
        conn = db.get_db()
        domains = set(r['domain'] for r in conn.execute(
            "SELECT domain FROM world_building WHERE novel_id=1").fetchall())
        conn.close()
        assert '力量体系' in domains, f"Expected 力量体系 in domains: {domains}"


class TestPlotArcsInit:
    def test_pa_init_creates_entries(self, mock_novel, fresh_db):
        from content_db import init_plot_arcs_from_file
        result = init_plot_arcs_from_file('test_novel')
        assert result['created'] > 0
        conn = sqlite3.connect(db.DB_PATH)
        rows = conn.execute(
            "SELECT name, type FROM plot_arcs WHERE novel_id=1").fetchall()
        conn.close()
        assert len(rows) >= 1


class TestPacingInit:
    def test_pc_init_creates_entries(self, mock_novel, fresh_db):
        from content_db import init_pacing_from_outline
        result = init_pacing_from_outline('test_novel')
        assert result['created'] > 0
        conn = sqlite3.connect(db.DB_PATH)
        rows = conn.execute(
            "SELECT pace_type, emotion_target FROM pacing_control WHERE novel_id=1").fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_pc_init_correct_pace_type(self, mock_novel, fresh_db):
        from content_db import init_pacing_from_outline
        init_pacing_from_outline('test_novel')
        conn = sqlite3.connect(db.DB_PATH)
        row = conn.execute(
            "SELECT pace_type FROM pacing_control WHERE novel_id=1 AND chapter_start=1").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == '铺垫'  # Chapter 1 says "节奏：铺垫"


class TestRevelationInit:
    def test_rs_init_creates_entries(self, mock_novel, fresh_db):
        from content_db import init_revelation_from_outline
        result = init_revelation_from_outline('test_novel')
        assert result['created'] > 0
        conn = sqlite3.connect(db.DB_PATH)
        rows = conn.execute(
            "SELECT name FROM revelation_schedule WHERE novel_id=1").fetchall()
        conn.close()
        assert len(rows) >= 1


class TestFullInit:
    """Test the orchestrated full initialization"""

    def test_full_init_returns_summary(self, mock_novel, fresh_db):
        """Full init should populate all tables and return summary"""
        from content_db import init_all_from_files
        result = init_all_from_files('test_novel')
        assert result['success'] is True
        assert 'world_building' in result['tables']
        assert 'plot_arcs' in result['tables']
        assert 'pacing_control' in result['tables']
        assert 'revelation_schedule' in result['tables']
        assert 'characters' in result['tables']

    def test_full_init_is_idempotent(self, mock_novel, fresh_db):
        from content_db import init_all_from_files
        r1 = init_all_from_files('test_novel')
        r2 = init_all_from_files('test_novel')  # Second call
        assert r2['success'] is True
        # Second init should not duplicate entries
        for table in ['world_building', 'plot_arcs', 'pacing_control']:
            assert r2['tables'][table] <= r1['tables'][table] + 1, \
                f"{table}: {r1['tables'][table]} → {r2['tables'][table]} (should not grow)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
