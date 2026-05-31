"""Unified initial schema — all 26 tables from content + config + usage DBs.

Revision ID: 0001_initial
Revises: None
Create Date: 2026-05-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── content.db tables ──

    op.create_table(
        "novels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("title", sa.String(), default=""),
        sa.Column("genre", sa.String(), default=""),
        sa.Column("subgenre", sa.String(), default=""),
        sa.Column("word_goal", sa.String(), default=""),
        sa.Column("total_chapters", sa.Integer(), default=0),
        sa.Column("total_words", sa.Integer(), default=0),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "outlines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), default=0),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "volume", name="uq_outlines_novel_volume"),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume", sa.String(), nullable=False),
        sa.Column("chapter_num", sa.Integer(), nullable=False),
        sa.Column("chapter_ref", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("title", sa.String(), default=""),
        sa.Column("word_count", sa.Integer(), default=0),
        sa.Column("content_hash", sa.String(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.Column("pace_type", sa.String(), default=""),
        sa.Column("emotional_beat", sa.String(), default=""),
        sa.Column("foreshadowing_touched", sa.String(), default="[]"),
        sa.Column("characters_appeared", sa.String(), default="[]"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "chapter_ref", name="uq_chapters_novel_ref"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_ref", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ai_review", sa.Text(), default=""),
        sa.Column("script_analyze_ok", sa.Integer(), default=0),
        sa.Column("script_compliance_ok", sa.Integer(), default=0),
        sa.Column("script_forbidden_ok", sa.Integer(), default=0),
        sa.Column("script_detail", sa.Text(), default=""),
        sa.Column("word_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.Text()),
        sa.Column("wc_ok", sa.Integer(), default=0),
        sa.Column("compliance_ok", sa.Integer(), default=0),
        sa.Column("forbidden_ok", sa.Integer(), default=0),
        sa.Column("bcontrast_count", sa.Integer(), default=0),
        sa.Column("judgment_groups", sa.Integer(), default=0),
        sa.Column("tell_count", sa.Integer(), default=0),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "chapter_ref", "created_at", name="uq_reviews_novel_ref_created"),
    )

    op.create_table(
        "danger_issues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume", sa.String(), nullable=False),
        sa.Column("chapter_num", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "volume", "chapter_num", name="uq_danger_novel_vol_ch"),
    )

    op.create_table(
        "foreshadowing",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("category", sa.String(), default="剧情"),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("introduced_vol", sa.Integer(), default=0),
        sa.Column("introduced_ch", sa.Integer(), default=0),
        sa.Column("target_vol", sa.Integer(), default=0),
        sa.Column("target_ch", sa.Integer(), default=0),
        sa.Column("resolved_vol", sa.Integer(), default=0),
        sa.Column("resolved_ch", sa.Integer(), default=0),
        sa.Column("resolution_note", sa.Text(), default=""),
        sa.Column("priority", sa.String(), default="normal"),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.Column("hint_method", sa.String(), default=""),
        sa.Column("reveal_method", sa.String(), default=""),
        sa.Column("is_dark", sa.Integer(), default=0),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), default="配角"),
        sa.Column("gender", sa.String(), default=""),
        sa.Column("age", sa.String(), default=""),
        sa.Column("identity", sa.String(), default=""),
        sa.Column("personality", sa.String(), default=""),
        sa.Column("appearance", sa.String(), default=""),
        sa.Column("background", sa.String(), default=""),
        sa.Column("current_status", sa.String(), default=""),
        sa.Column("current_vol", sa.Integer(), default=0),
        sa.Column("current_ch", sa.Integer(), default=0),
        sa.Column("lifeline", sa.Text(), default=""),
        sa.Column("arc", sa.Text(), default=""),
        sa.Column("ending", sa.Text(), default=""),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.Column("emotional_state", sa.String(), default=""),
        sa.Column("ability_level", sa.String(), default=""),
        sa.Column("relationship_map", sa.String(), default="[]"),
        sa.Column("desire", sa.String(), default=""),
        sa.Column("fear", sa.String(), default=""),
        sa.Column("lie", sa.String(), default=""),
        sa.Column("truth", sa.String(), default=""),
        sa.Column("ability_curve", sa.String(), default=""),
        sa.Column("ability_cost", sa.String(), default=""),
        sa.Column("emotion_curve", sa.String(), default=""),
        sa.Column("dilemma", sa.String(), default=""),
        sa.Column("mirror", sa.String(), default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chars_novel", "characters", ["novel_id"])

    op.create_table(
        "character_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(), default="状态变更"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("vol", sa.Integer(), default=0),
        sa.Column("ch", sa.Integer(), default=0),
        sa.Column("chapter_ref", sa.String(), default=""),
        sa.Column("source", sa.String(), default="manual"),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chevents_char", "character_events", ["character_id"])

    op.create_table(
        "world_building",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(), nullable=False, default=""),
        sa.Column("name", sa.String(), nullable=False, default=""),
        sa.Column("content", sa.Text(), nullable=False, default=""),
        sa.Column("related_vol", sa.Integer(), default=0),
        sa.Column("related_ch", sa.Integer(), default=0),
        sa.Column("tags", sa.String(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wb_novel", "world_building", ["novel_id"])
    op.create_index("idx_wb_domain", "world_building", ["domain"])

    op.create_table(
        "plot_arcs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False, default=""),
        sa.Column("type", sa.String(), default="主线"),
        sa.Column("volume_start", sa.Integer(), default=0),
        sa.Column("chapter_start", sa.Integer(), default=0),
        sa.Column("volume_end", sa.Integer(), default=0),
        sa.Column("chapter_end", sa.Integer(), default=0),
        sa.Column("summary", sa.Text(), default=""),
        sa.Column("milestones", sa.String(), default="[]"),
        sa.Column("status", sa.String(), default="active"),
        sa.Column("priority", sa.String(), default="normal"),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pa_novel", "plot_arcs", ["novel_id"])

    op.create_table(
        "pacing_control",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume", sa.Integer(), default=0),
        sa.Column("chapter_start", sa.Integer(), default=0),
        sa.Column("chapter_end", sa.Integer(), default=0),
        sa.Column("pace_type", sa.String(), default="过渡"),
        sa.Column("intensity", sa.Integer(), default=5),
        sa.Column("emotion_target", sa.String(), default=""),
        sa.Column("word_budget_min", sa.Integer(), default=2500),
        sa.Column("word_budget_max", sa.Integer(), default=3500),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pc_novel", "pacing_control", ["novel_id"])

    op.create_table(
        "revelation_schedule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False, default=""),
        sa.Column("info_type", sa.String(), default="世界观"),
        sa.Column("reveal_volume", sa.Integer(), default=0),
        sa.Column("reveal_chapter", sa.Integer(), default=0),
        sa.Column("content", sa.Text(), default=""),
        sa.Column("audience_knows", sa.Integer(), default=0),
        sa.Column("protagonist_knows", sa.Integer(), default=0),
        sa.Column("priority", sa.String(), default="normal"),
        sa.Column("created_at", sa.Text()),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rs_novel", "revelation_schedule", ["novel_id"])

    op.create_table(
        "genre_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_category", sa.String(), nullable=False, default=""),
        sa.Column("rule_content", sa.Text(), nullable=False, default=""),
        sa.Column("is_required", sa.Integer(), default=1),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gr_novel", "genre_rules", ["novel_id"])

    op.create_table(
        "story_volumes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vol_num", sa.Integer(), nullable=False, default=0),
        sa.Column("vol_name", sa.String(), default=""),
        sa.Column("word_range", sa.String(), default=""),
        sa.Column("goal", sa.Text(), default=""),
        sa.Column("conflict", sa.Text(), default=""),
        sa.Column("payoff", sa.Text(), default=""),
        sa.Column("foreshadowing", sa.Text(), default=""),
        sa.Column("status", sa.String(), default="待规划"),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sv_novel", "story_volumes", ["novel_id"])

    op.create_table(
        "volume_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vol_num", sa.Integer(), nullable=False, default=0),
        sa.Column("title", sa.String(), default=""),
        sa.Column("plan_content", sa.Text(), nullable=False, default=""),
        sa.Column("word_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "vol_num", name="uq_volume_plans_novel_vol"),
    )
    op.create_index("idx_vp_novel", "volume_plans", ["novel_id"])

    op.create_table(
        "alias_names",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(), default=""),
        sa.Column("alias_name", sa.String(), nullable=False, default=""),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("scope", sa.String(), default="全书"),
        sa.Column("first_chapter", sa.String(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_an_novel", "alias_names", ["novel_id"])

    op.create_table(
        "project_meta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meta_key", sa.String(), nullable=False),
        sa.Column("meta_value", sa.Text(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "meta_key", name="uq_project_meta_novel_key"),
    )
    op.create_index("idx_pm_novel", "project_meta", ["novel_id"])

    # ── config.db tables ──

    op.create_table(
        "banned_words",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(), unique=True, nullable=False),
        sa.Column("category", sa.String(), default="通用"),
        sa.Column("replacement", sa.String(), default=""),
        sa.Column("severity", sa.String(), default="error"),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_key", sa.String(), unique=True, nullable=False),
        sa.Column("rule_value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("category", sa.String(), default="general"),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "alias_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("real_name", sa.String(), unique=True, nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column("category", sa.String(), default="地名"),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "style_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Integer(), default=1),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deepseek_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(), unique=True, nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── usage.db tables ──

    op.create_table(
        "usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("novel", sa.String(), default=""),
        sa.Column("prompt_tokens", sa.Integer(), default=0),
        sa.Column("completion_tokens", sa.Integer(), default=0),
        sa.Column("total_tokens", sa.Integer(), default=0),
        sa.Column("cost_estimate", sa.Float(), default=0.0),
        sa.Column("created_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_usage_created_at", "usage", ["created_at"])
    op.create_index("idx_usage_operation", "usage", ["operation"])
    op.create_index("idx_usage_model", "usage", ["model"])

    op.create_table(
        "daily_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.String(), unique=True, nullable=False),
        sa.Column("total_calls", sa.Integer(), default=0),
        sa.Column("total_prompt_tokens", sa.Integer(), default=0),
        sa.Column("total_completion_tokens", sa.Integer(), default=0),
        sa.Column("total_tokens", sa.Integer(), default=0),
        sa.Column("total_cost", sa.Float(), default=0.0),
        sa.Column("by_operation", sa.Text(), default="{}"),
        sa.Column("by_model", sa.Text(), default="{}"),
        sa.Column("updated_at", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_daily_stats_date", "daily_stats", ["date"])

    # ── MySQL FULLTEXT indexes (only created for MySQL, skip for SQLite) ──
    # These are created conditionally in the application layer


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("daily_stats")
    op.drop_table("usage")
    op.drop_table("deepseek_config")
    op.drop_table("style_presets")
    op.drop_table("alias_registry")
    op.drop_table("compliance_rules")
    op.drop_table("banned_words")
    op.drop_table("project_meta")
    op.drop_table("alias_names")
    op.drop_table("volume_plans")
    op.drop_table("story_volumes")
    op.drop_table("genre_rules")
    op.drop_table("revelation_schedule")
    op.drop_table("pacing_control")
    op.drop_table("plot_arcs")
    op.drop_table("world_building")
    op.drop_table("character_events")
    op.drop_table("characters")
    op.drop_table("foreshadowing")
    op.drop_table("danger_issues")
    op.drop_table("reviews")
    op.drop_table("chapters")
    op.drop_table("outlines")
    op.drop_table("novels")
