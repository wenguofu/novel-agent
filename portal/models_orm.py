"""
SQLAlchemy ORM Models — dialect-agnostic declarative models for all tables.

Covers content.db, config.db, and usage.db tables.
Exact schema match with existing SQLite tables, with MySQL-compatible types.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    ForeignKey, UniqueConstraint, Index, event,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════
# content.db Tables
# ═══════════════════════════════════════════════════════════════════════════

class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    title = Column(String, default="")
    genre = Column(String, default="")
    subgenre = Column(String, default="")
    word_goal = Column(String, default="")
    total_chapters = Column(Integer, default=0)
    total_words = Column(Integer, default=0)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Relationships
    outlines = relationship("Outline", back_populates="novel", cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="novel", cascade="all, delete-orphan")
    danger_issues = relationship("DangerIssue", back_populates="novel", cascade="all, delete-orphan")
    story_tracking = relationship("StoryTracking", back_populates="novel", cascade="all, delete-orphan")
    foreshadowings = relationship("Foreshadowing", back_populates="novel", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="novel", cascade="all, delete-orphan")
    character_events = relationship("CharacterEvent", back_populates="novel", cascade="all, delete-orphan")
    world_buildings = relationship("WorldBuilding", back_populates="novel", cascade="all, delete-orphan")
    plot_arcs = relationship("PlotArc", back_populates="novel", cascade="all, delete-orphan")
    pacing_controls = relationship("PacingControl", back_populates="novel", cascade="all, delete-orphan")
    revelation_schedules = relationship("RevelationSchedule", back_populates="novel", cascade="all, delete-orphan")
    genre_rules = relationship("GenreRule", back_populates="novel", cascade="all, delete-orphan")
    story_volumes = relationship("StoryVolume", back_populates="novel", cascade="all, delete-orphan")
    volume_plans = relationship("VolumePlan", back_populates="novel", cascade="all, delete-orphan")
    alias_names = relationship("AliasName", back_populates="novel", cascade="all, delete-orphan")
    project_metas = relationship("ProjectMeta", back_populates="novel", cascade="all, delete-orphan")
    chapter_outlines = relationship("ChapterOutline", back_populates="novel", cascade="all, delete-orphan")


class ChapterOutline(Base):
    __tablename__ = "chapter_outlines"
    __table_args__ = (
        UniqueConstraint("novel_id", "volume", "chapter_num", name="uq_chapter_outlines_novel_vol_ch"),
        Index("idx_co_novel_vol", "novel_id", "volume"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume = Column(String, nullable=False)
    chapter_num = Column(Integer, nullable=False)
    title = Column(String, default="")
    function = Column(Text, default="[]")          # JSON array
    core_events = Column(Text, default="")
    foreshadowing = Column(Text, default="[]")    # JSON array
    ending_hook = Column(Text, default="")
    is_danger_scene = Column(Integer, default=0)  # 0/1
    word_count = Column(Integer, default=0)
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="chapter_outlines")


class Outline(Base):
    __tablename__ = "outlines"
    __table_args__ = (
        UniqueConstraint("novel_id", "volume", name="uq_outlines_novel_volume"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="outlines")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("novel_id", "chapter_ref", name="uq_chapters_novel_ref"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume = Column(String, nullable=False)
    chapter_num = Column(Integer, nullable=False)
    chapter_ref = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    title = Column(String, default="")
    word_count = Column(Integer, default=0)
    content_hash = Column(String, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # v3 extended columns
    pace_type = Column(String, default="")
    emotional_beat = Column(String, default="")
    foreshadowing_touched = Column(String, default="[]")
    characters_appeared = Column(String, default="[]")

    novel = relationship("Novel", back_populates="chapters")
    reviews = relationship("Review", back_populates="chapter", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("novel_id", "chapter_ref", "created_at", name="uq_reviews_novel_ref_created"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_ref = Column(String, nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    ai_review = Column(Text, default="")
    script_analyze_ok = Column(Integer, default=0)
    script_compliance_ok = Column(Integer, default=0)
    script_forbidden_ok = Column(Integer, default=0)
    script_detail = Column(Text, default="")
    word_count = Column(Integer, default=0)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # v3.1 quality tracking columns
    wc_ok = Column(Integer, default=0)
    compliance_ok = Column(Integer, default=0)
    forbidden_ok = Column(Integer, default=0)
    bcontrast_count = Column(Integer, default=0)
    judgment_groups = Column(Integer, default=0)
    tell_count = Column(Integer, default=0)

    novel = relationship("Novel", back_populates="reviews")
    chapter = relationship("Chapter", back_populates="reviews")


class DangerIssue(Base):
    __tablename__ = "danger_issues"
    __table_args__ = (
        UniqueConstraint("novel_id", "volume", "chapter_num", name="uq_danger_novel_vol_ch"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume = Column(String, nullable=False)
    chapter_num = Column(Integer, nullable=True)
    danger_level = Column(String, default="low")
    core_danger = Column(Text, default="")
    content = Column(Text, nullable=False)
    rhythm_data = Column(Text, default="{}")     # JSON
    foreshadowing_data = Column(Text, default="[]")  # JSON
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="danger_issues")


class StoryTracking(Base):
    __tablename__ = "story_tracking"
    __table_args__ = (
        UniqueConstraint("novel_id", "record_type", "record_key", name="uq_st_novel_type_key"),
        Index("idx_st_novel_type", "novel_id", "record_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    record_type = Column(String, nullable=False)
    record_key = Column(String, nullable=False)
    record_value = Column(Text, nullable=False)
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel")


class Foreshadowing(Base):
    __tablename__ = "foreshadowing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="剧情")
    status = Column(String, default="pending")
    introduced_vol = Column(Integer, default=0)
    introduced_ch = Column(Integer, default=0)
    target_vol = Column(Integer, default=0)
    target_ch = Column(Integer, default=0)
    resolved_vol = Column(Integer, default=0)
    resolved_ch = Column(Integer, default=0)
    resolution_note = Column(Text, default="")
    priority = Column(String, default="normal")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # v3 extended columns
    hint_method = Column(String, default="")
    reveal_method = Column(String, default="")
    is_dark = Column(Integer, default=0)

    novel = relationship("Novel", back_populates="foreshadowings")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        Index("idx_chars_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="配角")
    gender = Column(String, default="")
    age = Column(String, default="")
    identity = Column(String, default="")
    personality = Column(String, default="")
    appearance = Column(String, default="")
    background = Column(String, default="")
    current_status = Column(String, default="")
    current_vol = Column(Integer, default=0)
    current_ch = Column(Integer, default=0)
    lifeline = Column(Text, default="")
    arc = Column(Text, default="")
    ending = Column(Text, default="")
    notes = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # v3 extended columns
    emotional_state = Column(String, default="")
    ability_level = Column(String, default="")
    relationship_map = Column(String, default="[]")
    # v3.1 8-dimension profile
    desire = Column(String, default="")
    fear = Column(String, default="")
    lie = Column(String, default="")
    truth = Column(String, default="")
    ability_curve = Column(String, default="")
    ability_cost = Column(String, default="")
    emotion_curve = Column(String, default="")
    dilemma = Column(String, default="")
    mirror = Column(String, default="")

    novel = relationship("Novel", back_populates="characters")
    events = relationship("CharacterEvent", back_populates="character", cascade="all, delete-orphan")


class CharacterEvent(Base):
    __tablename__ = "character_events"
    __table_args__ = (
        Index("idx_chevents_char", "character_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, default="状态变更")
    description = Column(Text, nullable=False)
    vol = Column(Integer, default=0)
    ch = Column(Integer, default=0)
    chapter_ref = Column(String, default="")
    source = Column(String, default="manual")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="character_events")
    character = relationship("Character", back_populates="events")


class WorldBuilding(Base):
    __tablename__ = "world_building"
    __table_args__ = (
        Index("idx_wb_novel", "novel_id"),
        Index("idx_wb_domain", "domain"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    domain = Column(String, nullable=False, default="")
    name = Column(String, nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    related_vol = Column(Integer, default=0)
    related_ch = Column(Integer, default=0)
    tags = Column(String, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="world_buildings")


class PlotArc(Base):
    __tablename__ = "plot_arcs"
    __table_args__ = (
        Index("idx_pa_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, default="")
    type = Column(String, default="主线")
    volume_start = Column(Integer, default=0)
    chapter_start = Column(Integer, default=0)
    volume_end = Column(Integer, default=0)
    chapter_end = Column(Integer, default=0)
    summary = Column(Text, default="")
    milestones = Column(String, default="[]")
    status = Column(String, default="active")
    priority = Column(String, default="normal")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="plot_arcs")


class PacingControl(Base):
    __tablename__ = "pacing_control"
    __table_args__ = (
        Index("idx_pc_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume = Column(Integer, default=0)
    chapter_start = Column(Integer, default=0)
    chapter_end = Column(Integer, default=0)
    pace_type = Column(String, default="过渡")
    intensity = Column(Integer, default=5)
    emotion_target = Column(String, default="")
    word_budget_min = Column(Integer, default=2500)
    word_budget_max = Column(Integer, default=3500)
    notes = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="pacing_controls")


class RevelationSchedule(Base):
    __tablename__ = "revelation_schedule"
    __table_args__ = (
        Index("idx_rs_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, default="")
    info_type = Column(String, default="世界观")
    reveal_volume = Column(Integer, default=0)
    reveal_chapter = Column(Integer, default=0)
    content = Column(Text, default="")
    audience_knows = Column(Integer, default=0)
    protagonist_knows = Column(Integer, default=0)
    priority = Column(String, default="normal")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="revelation_schedules")


class GenreRule(Base):
    __tablename__ = "genre_rules"
    __table_args__ = (
        Index("idx_gr_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    rule_category = Column(String, nullable=False, default="")
    rule_content = Column(Text, nullable=False, default="")
    is_required = Column(Integer, default=1)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="genre_rules")


class StoryVolume(Base):
    __tablename__ = "story_volumes"
    __table_args__ = (
        Index("idx_sv_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    vol_num = Column(Integer, nullable=False, default=0)
    vol_name = Column(String, default="")
    word_range = Column(String, default="")
    goal = Column(Text, default="")
    conflict = Column(Text, default="")
    payoff = Column(Text, default="")
    foreshadowing = Column(Text, default="")
    status = Column(String, default="待规划")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="story_volumes")


class VolumePlan(Base):
    __tablename__ = "volume_plans"
    __table_args__ = (
        UniqueConstraint("novel_id", "vol_num", name="uq_volume_plans_novel_vol"),
        Index("idx_vp_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    vol_num = Column(Integer, nullable=False, default=0)
    title = Column(String, default="")
    plan_content = Column(Text, nullable=False, default="")
    word_count = Column(Integer, default=0)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="volume_plans")


class AliasName(Base):
    __tablename__ = "alias_names"
    __table_args__ = (
        Index("idx_an_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, default="")
    alias_name = Column(String, nullable=False, default="")
    description = Column(Text, default="")
    scope = Column(String, default="全书")
    first_chapter = Column(String, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="alias_names")


class ProjectMeta(Base):
    __tablename__ = "project_meta"
    __table_args__ = (
        UniqueConstraint("novel_id", "meta_key", name="uq_project_meta_novel_key"),
        Index("idx_pm_novel", "novel_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    meta_key = Column(String, nullable=False)
    meta_value = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    novel = relationship("Novel", back_populates="project_metas")


# ═══════════════════════════════════════════════════════════════════════════
# config.db Tables
# ═══════════════════════════════════════════════════════════════════════════

class BannedWord(Base):
    __tablename__ = "banned_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String, unique=True, nullable=False)
    category = Column(String, default="通用")
    replacement = Column(String, default="")
    severity = Column(String, default="error")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class ComplianceRule(Base):
    __tablename__ = "compliance_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_key = Column(String, unique=True, nullable=False)
    rule_value = Column(Text, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="general")
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class AliasRegistry(Base):
    """Config-level alias registry (global banned → alias mappings, distinct from novel-level alias_names)."""
    __tablename__ = "alias_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    real_name = Column(String, unique=True, nullable=False)
    alias = Column(String, nullable=False)
    category = Column(String, default="地名")
    notes = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class StylePreset(Base):
    __tablename__ = "style_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    prompt = Column(Text, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class CurrentStatus(Base):
    """Per-novel running narrative state (Layer 1.5 of context_builder).

    Replaces the file-based `novels/{name}/state/current_status.md` so the
    state can be queried, versioned and updated transactionally. The old
    file is kept as a read-only backup until manual cleanup.

    Schema:
      - `current_volume` / `current_chapter`: actual progress in the manuscript
      - `target_volume` / `target_chapter`: override for the current writing
        task (e.g. "重写第 1 章" while real progress is at vol 312)
      - `protagonist_state`, `key_tasks`, `current_crisis`: structured
        short fields the LLM can scan at a glance
      - `raw_md`: full free-form prose (from the original .md file) — used
        by Layer 1.5 when structured fields are empty
    """
    __tablename__ = "current_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id", ondelete="CASCADE"),
                       unique=True, nullable=False)
    current_volume = Column(Integer, default=1)
    current_chapter = Column(Integer, default=1)
    target_volume = Column(Integer, default=0)   # 0 = no override
    target_chapter = Column(Integer, default=0)
    total_word_count = Column(Integer, default=0)
    protagonist_state = Column(Text, default="")
    key_tasks = Column(Text, default="")          # newline-separated
    current_crisis = Column(Text, default="")
    raw_md = Column(Text, default="")
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DeepSeekConfig(Base):
    __tablename__ = "deepseek_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String, unique=True, nullable=False)
    config_value = Column(Text, nullable=False)
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ═══════════════════════════════════════════════════════════════════════════
# usage.db Tables
# ═══════════════════════════════════════════════════════════════════════════

class UsageRecord(Base):
    __tablename__ = "usage"
    __table_args__ = (
        Index("idx_usage_created_at", "created_at"),
        Index("idx_usage_operation", "operation"),
        Index("idx_usage_model", "model"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    novel = Column(String, default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)
    created_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        Index("idx_daily_stats_date", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, unique=True, nullable=False)
    total_calls = Column(Integer, default=0)
    total_prompt_tokens = Column(Integer, default=0)
    total_completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    by_operation = Column(Text, default="{}")
    by_model = Column(Text, default="{}")
    updated_at = Column(Text, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ═══════════════════════════════════════════════════════════════════════════
# Engine / Session Helpers
# ═══════════════════════════════════════════════════════════════════════════

def create_all(engine):
    """Create all tables in the database. Idempotent (uses CREATE IF NOT EXISTS)."""
    Base.metadata.create_all(engine)


def get_bind_urls():
    """Return ``(content_url, config_url, usage_url)``.

    In MySQL mode (the only supported mode), all three return the same
    MySQL URL. SQLite side-DB support was removed in v3.4 — see
    ``openspec/changes/remove-sqlite-use-mysql-only/``.
    """
    import os
    db_url = os.environ.get("DATABASE_URL", "")
    return db_url, db_url, db_url  # Single MySQL DB
