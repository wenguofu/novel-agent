"""
Repository Layer — thin wrapper around SQLAlchemy ORM models.

Provides dict-based API for backward compatibility with content_db.py callers.
All DB operations go through here; no raw sqlite3 anywhere else.

Usage:
    from repository import get_repo
    repo = get_repo()
    chars = repo.list_characters("novel_name")
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any, Generator

from sqlalchemy import text, and_, or_, func
from sqlalchemy.orm import Session, joinedload

from db import get_engine, get_session_factory
from models_orm import (
    Base, Novel, Outline, Chapter, Review, DangerIssue,
    Foreshadowing, Character, CharacterEvent, WorldBuilding,
    PlotArc, PacingControl, RevelationSchedule, GenreRule,
    StoryVolume, VolumePlan, AliasName, ProjectMeta,
    BannedWord, ComplianceRule, AliasRegistry, StylePreset, DeepSeekConfig,
    UsageRecord, DailyStat,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row, exclude=None):
    """Convert ORM object to dict, excluding SQLAlchemy internal state."""
    if row is None:
        return None
    exclude = set(exclude or []) | {"_sa_instance_state"}
    return {
        c.key: getattr(row, c.key)
        for c in row.__table__.columns
        if c.key not in exclude
    }


def _rows_to_dicts(rows):
    """Convert list of ORM objects to list of dicts."""
    return [_row_to_dict(r) for r in rows]


# ── Session Management ───────────────────────────────────────────────────

@contextmanager
def repo_session() -> Generator[Session, None, None]:
    """Get a session with auto-commit/rollback."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Repository ───────────────────────────────────────────────────────────

class Repository:
    """Unified data access layer for all tables."""

    def __init__(self):
        self._factory = get_session_factory()

    # ── Generic helpers ────────────────────────────────────────────

    def _get_novel_id(self, session: Session, novel_name: str) -> Optional[int]:
        row = session.query(Novel.id).filter(Novel.name == novel_name).first()
        return row[0] if row else None

    def _get_novel(self, session: Session, novel_name: str) -> Optional[Novel]:
        return session.query(Novel).filter(Novel.name == novel_name).first()

    def _upsert(self, session, model, lookup: dict, values: dict):
        """Generic upsert: find by lookup keys, update or create."""
        instance = session.query(model).filter_by(**lookup).first()
        if instance:
            for k, v in values.items():
                setattr(instance, k, v)
            if hasattr(model, 'updated_at'):
                setattr(instance, 'updated_at', _now())
        else:
            merged = {**lookup, **values}
            if hasattr(model, 'created_at') and 'created_at' not in merged:
                merged['created_at'] = _now()
            if hasattr(model, 'updated_at') and 'updated_at' not in merged:
                merged['updated_at'] = _now()
            instance = model(**merged)
            session.add(instance)
        session.flush()
        return instance

    # ═══════════════════════════════════════════════════════════════
    # Novel
    # ═══════════════════════════════════════════════════════════════

    def get_novel(self, novel_name: str) -> Optional[Dict]:
        with repo_session() as s:
            n = s.query(Novel).filter(Novel.name == novel_name).first()
            return _row_to_dict(n)

    def get_novel_by_id(self, nid: int) -> Optional[Dict]:
        with repo_session() as s:
            n = s.query(Novel).filter(Novel.id == nid).first()
            return _row_to_dict(n)

    def upsert_novel(self, novel_name: str, **kwargs) -> Dict:
        with repo_session() as s:
            n = s.query(Novel).filter(Novel.name == novel_name).first()
            if n:
                for k, v in kwargs.items():
                    if hasattr(Novel, k):
                        setattr(n, k, v)
                n.updated_at = _now()
            else:
                kwargs['name'] = novel_name
                kwargs.setdefault('created_at', _now())
                kwargs.setdefault('updated_at', _now())
                n = Novel(**kwargs)
                s.add(n)
            s.flush()
            return _row_to_dict(n)

    def list_novels(self) -> List[Dict]:
        with repo_session() as s:
            rows = s.query(Novel).order_by(Novel.name).all()
            return _rows_to_dicts(rows)

    def delete_novel(self, novel_name: str):
        with repo_session() as s:
            n = s.query(Novel).filter(Novel.name == novel_name).first()
            if n:
                s.delete(n)

    # ═══════════════════════════════════════════════════════════════
    # Outline
    # ═══════════════════════════════════════════════════════════════

    def get_outline(self, novel_name: str, volume: str) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            o = s.query(Outline).filter(Outline.novel_id == nid, Outline.volume == volume).first()
            return _row_to_dict(o)

    def list_outlines(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(Outline).filter(Outline.novel_id == nid).order_by(Outline.volume).all()
            return _rows_to_dicts(rows)

    def upsert_outline(self, novel_name: str, volume: str, content: str, word_count: int = 0) -> Dict:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return {}
            o = self._upsert(s, Outline,
                           {"novel_id": nid, "volume": volume},
                           {"content": content, "word_count": word_count})
            return _row_to_dict(o)

    def delete_outline(self, novel_name: str, volume: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(Outline).filter(Outline.novel_id == nid, Outline.volume == volume).delete()

    # ═══════════════════════════════════════════════════════════════
    # Chapter
    # ═══════════════════════════════════════════════════════════════

    def get_chapter(self, novel_name: str, chapter_ref: str) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            ch = s.query(Chapter).filter(Chapter.novel_id == nid, Chapter.chapter_ref == chapter_ref).first()
            return _row_to_dict(ch)

    def get_chapter_by_num(self, novel_name: str, volume: str, chapter_num: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            ch = s.query(Chapter).filter(
                Chapter.novel_id == nid, Chapter.volume == volume,
                Chapter.chapter_num == chapter_num
            ).first()
            return _row_to_dict(ch)

    def list_chapters(self, novel_name: str, volume: Optional[str] = None) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(Chapter).filter(Chapter.novel_id == nid)
            if volume:
                q = q.filter(Chapter.volume == volume)
            rows = q.order_by(Chapter.volume, Chapter.chapter_num).all()
            return _rows_to_dicts(rows)

    def upsert_chapter(self, novel_name: str, chapter_ref: str, **kwargs) -> Dict:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return {}
            # Use chapter_ref as the lookup key (UNIQUE constraint)
            ch = s.query(Chapter).filter(Chapter.novel_id == nid, Chapter.chapter_ref == chapter_ref).first()
            if ch:
                for k, v in kwargs.items():
                    if hasattr(Chapter, k):
                        setattr(ch, k, v)
                ch.updated_at = _now()
            else:
                kwargs['novel_id'] = nid
                kwargs['chapter_ref'] = chapter_ref
                kwargs.setdefault('created_at', _now())
                kwargs.setdefault('updated_at', _now())
                ch = Chapter(**kwargs)
                s.add(ch)
            s.flush()
            return _row_to_dict(ch)

    def get_previous_chapter(self, novel_name: str, volume: str, chapter_num: int) -> Optional[Dict]:
        """Get the immediately preceding chapter for continuity."""
        return self.get_chapter_by_num(novel_name, volume, chapter_num - 1)

    def get_chapter_content_hash(self, novel_name: str, chapter_ref: str) -> Optional[str]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            row = s.query(Chapter.content_hash).filter(
                Chapter.novel_id == nid, Chapter.chapter_ref == chapter_ref
            ).first()
            return row[0] if row else None

    def get_recent_chapters(self, novel_name: str, limit: int = 10) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(Chapter).filter(Chapter.novel_id == nid)\
                     .order_by(Chapter.volume.desc(), Chapter.chapter_num.desc())\
                     .limit(limit).all()
            return list(reversed(_rows_to_dicts(rows)))

    # ═══════════════════════════════════════════════════════════════
    # Review
    # ═══════════════════════════════════════════════════════════════

    def get_review(self, novel_name: str, chapter_ref: str) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            r = s.query(Review).filter(
                Review.novel_id == nid, Review.chapter_ref == chapter_ref
            ).order_by(Review.created_at.desc()).first()
            return _row_to_dict(r)

    def list_reviews(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(Review).filter(Review.novel_id == nid)\
                     .order_by(Review.created_at.desc()).all()
            return _rows_to_dicts(rows)

    def upsert_review(self, novel_name: str, chapter_ref: str, **kwargs) -> Dict:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return {}
            r = s.query(Review).filter(
                Review.novel_id == nid, Review.chapter_ref == chapter_ref
            ).order_by(Review.created_at.desc()).first()
            if r and kwargs.get("ai_review"):
                # Update existing
                for k, v in kwargs.items():
                    if hasattr(Review, k):
                        setattr(r, k, v)
                s.flush()
                return _row_to_dict(r)
            else:
                kwargs['novel_id'] = nid
                kwargs['chapter_ref'] = chapter_ref
                kwargs.setdefault('created_at', _now())
                r = Review(**kwargs)
                s.add(r)
                s.flush()
                return _row_to_dict(r)

    def get_review_count(self, novel_name: str) -> int:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return 0
            return s.query(Review).filter(Review.novel_id == nid).count()

    def update_chapter_metadata(self, novel_name: str, volume: str, chapter_num: int, **kwargs):
        """Update v3 chapter metadata (pace_type, emotional_beat, etc.)"""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(Chapter).filter(
                Chapter.novel_id == nid, Chapter.volume == volume,
                Chapter.chapter_num == chapter_num
            ).update(kwargs, synchronize_session=False)

    # ═══════════════════════════════════════════════════════════════
    # DangerIssue
    # ═══════════════════════════════════════════════════════════════

    def get_danger_issue(self, novel_name: str, volume: str, chapter_num: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            d = s.query(DangerIssue).filter(
                DangerIssue.novel_id == nid, DangerIssue.volume == volume,
                DangerIssue.chapter_num == chapter_num
            ).first()
            return _row_to_dict(d)

    # ═══════════════════════════════════════════════════════════════
    # Character
    # ═══════════════════════════════════════════════════════════════

    def get_character(self, novel_name: str, cid: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            c = s.query(Character).filter(Character.novel_id == nid, Character.id == cid).first()
            return _row_to_dict(c)

    def list_characters(self, novel_name: str, role: Optional[str] = None) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(Character).filter(Character.novel_id == nid)
            if role:
                q = q.filter(Character.role == role)
            # Order: protagonist first, then female lead, then villain, then others
            order_case = text("CASE role WHEN '主角' THEN 0 WHEN '女主' THEN 1 WHEN '反派' THEN 2 ELSE 3 END")
            rows = q.order_by(order_case, Character.name).all()
            return _rows_to_dicts(rows)

    def add_character(self, novel_name: str, name: str, role: str = "配角", **kwargs) -> Optional[int]:
        """Add a character, return id."""
        allowed = {
            "gender", "age", "identity", "personality", "appearance", "background",
            "current_status", "current_vol", "current_ch", "lifeline", "arc", "ending", "notes",
            "desire", "fear", "lie", "truth", "ability_level", "ability_curve", "ability_cost",
            "emotional_state", "emotion_curve", "relationship_map", "dilemma", "mirror",
        }
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            data = {"novel_id": nid, "name": name, "role": role,
                    "created_at": _now(), "updated_at": _now()}
            for k in allowed:
                if k in kwargs and kwargs[k]:
                    data[k] = kwargs[k]
            c = Character(**data)
            s.add(c)
            s.flush()
            return c.id

    def update_character(self, cid: int, **kwargs) -> bool:
        """Update character fields. Returns True if successful."""
        allowed = {
            "name", "role", "gender", "age", "identity", "personality", "appearance",
            "background", "current_status", "current_vol", "current_ch", "lifeline",
            "arc", "ending", "notes", "desire", "fear", "lie", "truth",
            "ability_level", "ability_curve", "ability_cost",
            "emotional_state", "emotion_curve", "relationship_map", "dilemma", "mirror",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = _now()
        with repo_session() as s:
            s.query(Character).filter(Character.id == cid).update(updates, synchronize_session=False)
        return True

    def delete_character(self, cid: int):
        with repo_session() as s:
            s.query(Character).filter(Character.id == cid).delete()

    def list_characters_active_in_volume(self, novel_name: str, volume: int) -> List[Dict]:
        """Characters whose current_vol is within ±1 of the given volume."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(Character).filter(
                Character.novel_id == nid,
                Character.current_vol.between(max(1, volume - 1), volume + 1)
            ).all()
            # Always include protagonist + female lead
            mains = s.query(Character).filter(
                Character.novel_id == nid,
                Character.role.in_(["主角", "女主"])
            ).all()
            all_chars = {c.id: c for c in rows}
            for c in mains:
                if c.id not in all_chars:
                    all_chars[c.id] = c
            order = {"主角": 0, "女主": 1, "反派": 2}
            result = sorted(all_chars.values(), key=lambda c: (order.get(c.role, 3), c.name))
            return _rows_to_dicts(result)

    # ═══════════════════════════════════════════════════════════════
    # CharacterEvent
    # ═══════════════════════════════════════════════════════════════

    def add_character_event(self, novel_name: str, cid: int, description: str,
                            event_type: str = "状态变更", vol: int = 0, ch: int = 0,
                            chapter_ref: str = "", source: str = "manual") -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            ce = CharacterEvent(novel_id=nid, character_id=cid, event_type=event_type,
                               description=description, vol=vol, ch=ch,
                               chapter_ref=chapter_ref, source=source, created_at=_now())
            s.add(ce)
            s.flush()
            return ce.id

    def list_character_events(self, cid: int, limit: int = 50) -> List[Dict]:
        with repo_session() as s:
            rows = s.query(CharacterEvent).filter(CharacterEvent.character_id == cid)\
                     .order_by(CharacterEvent.vol.asc(), CharacterEvent.ch.asc())\
                     .limit(limit).all()
            return _rows_to_dicts(rows)

    def get_recent_character_events(self, novel_name: str, volume: int, max_chapters: int = 20) -> List[Dict]:
        """Get character events from recent chapters for state tracking."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            min_vol = max(1, volume - 3)
            rows = s.query(CharacterEvent).filter(
                CharacterEvent.novel_id == nid,
                CharacterEvent.vol >= min_vol
            ).order_by(CharacterEvent.vol.desc(), CharacterEvent.ch.desc()).limit(max_chapters).all()
            return _rows_to_dicts(rows)

    # ═══════════════════════════════════════════════════════════════
    # Foreshadowing
    # ═══════════════════════════════════════════════════════════════

    def add_foreshadowing(self, novel_name: str, name: str, description: str = "",
                          category: str = "剧情", introduced_vol: int = 0, introduced_ch: int = 0,
                          target_vol: int = 0, target_ch: int = 0, priority: str = "normal") -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            f = Foreshadowing(novel_id=nid, name=name, description=description, category=category,
                             introduced_vol=introduced_vol, introduced_ch=introduced_ch,
                             target_vol=target_vol, target_ch=target_ch, priority=priority,
                             created_at=_now(), updated_at=_now())
            s.add(f)
            s.flush()
            return f.id

    def list_foreshadowing(self, novel_name: str, status: Optional[str] = None,
                           volume: Optional[int] = None, limit: int = 100) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(Foreshadowing).filter(Foreshadowing.novel_id == nid)
            if status:
                q = q.filter(Foreshadowing.status == status)
            if volume is not None:
                q = q.filter(
                    or_(Foreshadowing.target_vol == volume, Foreshadowing.introduced_vol == volume)
                )
            rows = q.order_by(Foreshadowing.priority.desc(), Foreshadowing.target_vol.asc(),
                            Foreshadowing.introduced_ch.asc()).limit(limit).all()
            return _rows_to_dicts(rows)

    def get_unresolved_foreshadowing(self, novel_name: str, current_vol: Optional[int] = None,
                                      current_ch: Optional[int] = None) -> List[Dict]:
        """Get unresolved foreshadowing that should be resolved soon."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(Foreshadowing).filter(
                Foreshadowing.novel_id == nid,
                ~Foreshadowing.status.in_(["resolved", "abandoned"])
            )
            if current_vol is not None:
                q = q.filter(
                    or_(
                        Foreshadowing.target_vol <= current_vol,
                        Foreshadowing.target_vol == 0,
                        Foreshadowing.introduced_vol == current_vol,
                    )
                )
            rows = q.order_by(Foreshadowing.priority.desc(), Foreshadowing.target_vol.asc(),
                            Foreshadowing.introduced_ch.asc()).all()
            return _rows_to_dicts(rows)

    def get_foreshadowing_for_volume(self, novel_name: str, volume: int) -> Dict[str, List[Dict]]:
        """Get foreshadowing scoped to a specific volume.
        Returns: {"due_now": [...], "overdue": [...], "recent": [...]}
        """
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return {"due_now": [], "overdue": [], "recent": []}

            pending = s.query(Foreshadowing).filter(
                Foreshadowing.novel_id == nid,
                ~Foreshadowing.status.in_(["resolved", "abandoned"])
            )

            # Due now: target_vol == current_vol
            due_now = pending.filter(Foreshadowing.target_vol == volume)\
                       .order_by(Foreshadowing.priority.desc()).limit(3).all()

            # Overdue: target_vol < current_vol
            overdue = pending.filter(Foreshadowing.target_vol < volume, Foreshadowing.target_vol > 0)\
                       .order_by(Foreshadowing.target_vol.desc()).limit(3).all()

            # Recent introductions
            recent = pending.filter(Foreshadowing.introduced_vol >= max(1, volume - 2))\
                       .order_by(Foreshadowing.introduced_vol.desc()).limit(2).all()

            return {
                "due_now": _rows_to_dicts(due_now),
                "overdue": _rows_to_dicts(overdue),
                "recent": _rows_to_dicts(recent),
            }

    def update_foreshadowing(self, fid: int, **kwargs) -> bool:
        allowed = {"name", "description", "category", "status", "introduced_vol",
                   "introduced_ch", "target_vol", "target_ch", "resolved_vol",
                   "resolved_ch", "resolution_note", "priority",
                   "hint_method", "reveal_method", "is_dark"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = _now()
        with repo_session() as s:
            s.query(Foreshadowing).filter(Foreshadowing.id == fid).update(updates, synchronize_session=False)
        return True

    def delete_foreshadowing(self, fid: int):
        with repo_session() as s:
            s.query(Foreshadowing).filter(Foreshadowing.id == fid).delete()

    def resolve_foreshadowing(self, fid: int, vol: int, ch: int, note: str = ""):
        with repo_session() as s:
            f = s.query(Foreshadowing).filter(Foreshadowing.id == fid).first()
            if f:
                f.status = "resolved"
                f.resolved_vol = vol
                f.resolved_ch = ch
                f.resolution_note = (f.resolution_note or "") + note
                f.updated_at = _now()

    def list_pending_foreshadowing(self, novel_name: str) -> List[Dict]:
        return self.list_foreshadowing(novel_name, status="pending")

    # ═══════════════════════════════════════════════════════════════
    # WorldBuilding
    # ═══════════════════════════════════════════════════════════════

    def list_world_building(self, novel_name: str, domain: Optional[str] = None) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(WorldBuilding).filter(WorldBuilding.novel_id == nid)
            if domain:
                q = q.filter(WorldBuilding.domain == domain)
            return _rows_to_dicts(q.all())

    def get_world_building_for_volume(self, novel_name: str, volume: int, limit: int = 5) -> List[Dict]:
        """Get world building entries relevant to current volume."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(WorldBuilding).filter(
                WorldBuilding.novel_id == nid,
                or_(
                    WorldBuilding.related_vol == 0,
                    WorldBuilding.related_vol.between(max(1, volume - 1), volume + 1),
                )
            ).limit(limit).all()
            return _rows_to_dicts(rows)

    def get_world_building_volume_plus_global(
        self, novel_name: str, volume: int, local_limit: int = 5, global_limit: int = 5
    ) -> List[Dict]:
        """Get local-volume world building (vol-1..vol+1) PLUS a global sample.

        The "global" half is the rest of the world's important settings
        (e.g. 八神体系 in 大强成神啦) that may be referenced even when the
        scene is set in an earlier volume. Without the global sample, late-
        stage lore that the LLM needs to foreshadow properly gets dropped.
        """
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            # Local: this volume's window (vol-1..vol+1) + global entries
            local_q = s.query(WorldBuilding).filter(
                WorldBuilding.novel_id == nid,
                or_(
                    WorldBuilding.related_vol == 0,
                    WorldBuilding.related_vol.between(max(1, volume - 1), volume + 1),
                )
            ).limit(local_limit)
            local_ids = {r.id for r in local_q.all()}

            # Global: entries related to later volumes (related_vol > vol+1)
            global_q = s.query(WorldBuilding).filter(
                WorldBuilding.novel_id == nid,
                WorldBuilding.related_vol > volume + 1,
                ~WorldBuilding.id.in_(local_ids),
            ).limit(global_limit)
            global_rows = global_q.all()

            # Re-fetch local to preserve order
            local_rows = s.query(WorldBuilding).filter(
                WorldBuilding.id.in_(local_ids)
            ).all()
            return _rows_to_dicts(local_rows) + _rows_to_dicts(global_rows)

    def add_world_building(self, novel_name: str, domain: str, name: str, content: str,
                           related_vol: int = 0, related_ch: int = 0, tags: str = "") -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            wb = WorldBuilding(novel_id=nid, domain=domain, name=name, content=content,
                              related_vol=related_vol, related_ch=related_ch, tags=tags,
                              created_at=_now(), updated_at=_now())
            s.add(wb)
            s.flush()
            return wb.id

    def clear_world_building(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(WorldBuilding).filter(WorldBuilding.novel_id == nid).delete()

    # ═══════════════════════════════════════════════════════════════
    # PlotArc
    # ═══════════════════════════════════════════════════════════════

    def list_plot_arcs(self, novel_name: str, status: Optional[str] = None) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            q = s.query(PlotArc).filter(PlotArc.novel_id == nid)
            if status:
                q = q.filter(PlotArc.status == status)
            return _rows_to_dicts(q.all())

    def get_plot_arcs_for_volume(self, novel_name: str, volume: int) -> List[Dict]:
        """Get active plot arcs spanning the current volume."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(PlotArc).filter(
                PlotArc.novel_id == nid,
                PlotArc.status == "active",
                PlotArc.volume_start <= volume,
                PlotArc.volume_end >= volume,
            ).limit(5).all()
            return _rows_to_dicts(rows)

    def add_plot_arc(self, novel_name: str, name: str, arc_type: str = "主线", **kwargs) -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            data = {"novel_id": nid, "name": name[:80], "type": arc_type,
                    "created_at": _now(), "updated_at": _now()}
            for k in ("volume_start", "volume_end", "chapter_start", "chapter_end",
                      "summary", "milestones", "status", "priority"):
                if k in kwargs:
                    data[k] = kwargs[k]
            pa = PlotArc(**data)
            s.add(pa)
            s.flush()
            return pa.id

    # ═══════════════════════════════════════════════════════════════
    # PacingControl
    # ═══════════════════════════════════════════════════════════════

    def get_pacing(self, novel_name: str, volume: int, chapter_num: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            row = s.query(PacingControl).filter(
                PacingControl.novel_id == nid,
                PacingControl.volume == volume,
                PacingControl.chapter_start <= chapter_num,
                PacingControl.chapter_end >= chapter_num,
            ).first()
            return _row_to_dict(row)

    def add_pacing(self, novel_name: str, volume: int, chapter_start: int, chapter_end: int, **kwargs):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            exists = s.query(PacingControl).filter(
                PacingControl.novel_id == nid, PacingControl.volume == volume,
                PacingControl.chapter_start == chapter_start
            ).first()
            if not exists:
                data = {"novel_id": nid, "volume": volume,
                       "chapter_start": chapter_start, "chapter_end": chapter_end,
                       "created_at": _now()}
                data.update(kwargs)
                pc = PacingControl(**data)
                s.add(pc)
                s.flush()
                return pc.id
        return None

    # ═══════════════════════════════════════════════════════════════
    # RevelationSchedule
    # ═══════════════════════════════════════════════════════════════

    def get_revelations_for_volume(self, novel_name: str, volume: int) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(RevelationSchedule).filter(
                RevelationSchedule.novel_id == nid,
                RevelationSchedule.reveal_volume == volume,
            ).limit(5).all()
            return _rows_to_dicts(rows)

    def add_revelation(self, novel_name: str, name: str, info_type: str = "世界观",
                       reveal_volume: int = 0, reveal_chapter: int = 0,
                       content: str = "", priority: str = "normal") -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            rs = RevelationSchedule(novel_id=nid, name=name, info_type=info_type,
                                    reveal_volume=reveal_volume, reveal_chapter=reveal_chapter,
                                    content=content, priority=priority,
                                    created_at=_now(), updated_at=_now())
            s.add(rs)
            s.flush()
            return rs.id

    # ═══════════════════════════════════════════════════════════════
    # GenreRule
    # ═══════════════════════════════════════════════════════════════

    def list_genre_rules(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            return _rows_to_dicts(
                s.query(GenreRule).filter(GenreRule.novel_id == nid).all()
            )

    def add_genre_rule(self, novel_name: str, rule_category: str, rule_content: str,
                       is_required: int = 1) -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            gr = GenreRule(novel_id=nid, rule_category=rule_category,
                          rule_content=rule_content, is_required=is_required,
                          created_at=_now())
            s.add(gr)
            s.flush()
            return gr.id

    def clear_genre_rules(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(GenreRule).filter(GenreRule.novel_id == nid).delete()

    # ═══════════════════════════════════════════════════════════════
    # StoryVolume
    # ═══════════════════════════════════════════════════════════════

    def list_story_volumes(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            return _rows_to_dicts(
                s.query(StoryVolume).filter(StoryVolume.novel_id == nid)\
                 .order_by(StoryVolume.vol_num).all()
            )

    def get_story_volume(self, novel_name: str, vol_num: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            sv = s.query(StoryVolume).filter(
                StoryVolume.novel_id == nid, StoryVolume.vol_num == vol_num
            ).first()
            return _row_to_dict(sv)

    def clear_story_volumes(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(StoryVolume).filter(StoryVolume.novel_id == nid).delete()

    def add_story_volume(self, novel_name: str, vol_num: int, **kwargs) -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            data = {"novel_id": nid, "vol_num": vol_num, "created_at": _now()}
            for k in ("vol_name", "word_range", "goal", "conflict", "payoff", "foreshadowing", "status"):
                data[k] = kwargs.get(k, "")
            sv = StoryVolume(**data)
            s.add(sv)
            s.flush()
            return sv.id

    # ═══════════════════════════════════════════════════════════════
    # VolumePlan
    # ═══════════════════════════════════════════════════════════════

    def get_volume_plan(self, novel_name: str, vol_num: int) -> Optional[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            vp = s.query(VolumePlan).filter(
                VolumePlan.novel_id == nid, VolumePlan.vol_num == vol_num
            ).first()
            return _row_to_dict(vp)

    def list_volume_plans(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            return _rows_to_dicts(
                s.query(VolumePlan).filter(VolumePlan.novel_id == nid)\
                 .order_by(VolumePlan.vol_num).all()
            )

    def upsert_volume_plan(self, novel_name: str, vol_num: int, **kwargs) -> Dict:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return {}
            vp = self._upsert(s, VolumePlan,
                            {"novel_id": nid, "vol_num": vol_num},
                            kwargs)
            return _row_to_dict(vp)

    def clear_volume_plans(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(VolumePlan).filter(VolumePlan.novel_id == nid).delete()

    # ═══════════════════════════════════════════════════════════════
    # AliasName (novel-level)
    # ═══════════════════════════════════════════════════════════════

    def list_alias_names(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            return _rows_to_dicts(
                s.query(AliasName).filter(AliasName.novel_id == nid).all()
            )

    def add_alias_name(self, novel_name: str, category: str, alias_name: str,
                       description: str = "", scope: str = "全书",
                       first_chapter: str = "") -> Optional[int]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            an = AliasName(novel_id=nid, category=category, alias_name=alias_name,
                          description=description, scope=scope,
                          first_chapter=first_chapter, created_at=_now())
            s.add(an)
            s.flush()
            return an.id

    def clear_alias_names(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(AliasName).filter(AliasName.novel_id == nid).delete()

    # ═══════════════════════════════════════════════════════════════
    # ProjectMeta
    # ═══════════════════════════════════════════════════════════════

    def get_project_meta(self, novel_name: str, key: str) -> Optional[str]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return None
            row = s.query(ProjectMeta).filter(
                ProjectMeta.novel_id == nid, ProjectMeta.meta_key == key
            ).first()
            return row.meta_value if row else None

    def list_project_meta(self, novel_name: str) -> List[Dict]:
        """Return all (meta_key, meta_value) rows for a novel.
        Used by context_builder Layer 1 to feed the full project setting
        (乐园, 八位古神, 叛神系统, ...) into the LLM prompt.
        """
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(ProjectMeta).filter(ProjectMeta.novel_id == nid).all()
            return [{"meta_key": r.meta_key, "meta_value": r.meta_value} for r in rows]

    def list_genre_rules(self, novel_name: str) -> List[Dict]:
        """Return all genre_rules for a novel. Empty list if novel has none.

        context_builder assembles these into the prompt so the LLM knows the
        type-level constraints (must-haves, pacing, reader expectations).
        """
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            rows = s.query(GenreRule).filter(GenreRule.novel_id == nid).all()
            return [
                {"rule_category": r.rule_category, "rule_content": r.rule_content,
                 "is_required": r.is_required}
                for r in rows
            ]

    def list_project_meta(self, novel_name: str) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            return _rows_to_dicts(
                s.query(ProjectMeta).filter(ProjectMeta.novel_id == nid).all()
            )

    def upsert_project_meta(self, novel_name: str, key: str, value: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            self._upsert(s, ProjectMeta,
                        {"novel_id": nid, "meta_key": key},
                        {"meta_value": value})

    def clear_project_meta(self, novel_name: str):
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return
            s.query(ProjectMeta).filter(ProjectMeta.novel_id == nid).delete()

    # ═══════════════════════════════════════════════════════════════
    # Search (dialect-aware fallback to LIKE)
    # ═══════════════════════════════════════════════════════════════

    def search_chapters(self, novel_name: str, query: str, limit: int = 20) -> List[Dict]:
        """Full-text search on chapters using LIKE fallback (FTS5 no longer used)."""
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            like = f"%{query}%"
            rows = s.query(Chapter).filter(
                Chapter.novel_id == nid,
                Chapter.content.like(like)
            ).order_by(Chapter.volume, Chapter.chapter_num).limit(limit).all()
            return [{
                "chapter_ref": r.chapter_ref,
                "title": r.title,
                "word_count": r.word_count,
                "volume": r.volume,
                "novel_name": novel_name,
            } for r in rows]

    def search_outlines(self, novel_name: str, query: str, limit: int = 20) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            like = f"%{query}%"
            rows = s.query(Outline).filter(
                Outline.novel_id == nid,
                Outline.content.like(like)
            ).limit(limit).all()
            return [{"volume": r.volume, "novel_name": novel_name} for r in rows]

    def search_reviews(self, novel_name: str, query: str, limit: int = 20) -> List[Dict]:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid: return []
            like = f"%{query}%"
            rows = s.query(Review).filter(
                Review.novel_id == nid,
                or_(Review.ai_review.like(like), Review.script_detail.like(like))
            ).limit(limit).all()
            return [{"chapter_ref": r.chapter_ref, "novel_name": novel_name, "word_count": r.word_count} for r in rows]

    def search_all(self, query: str, novel_name: str = None, limit: int = 20) -> Dict:
        """Search across chapters, outlines, reviews. Returns dict compatible with old content_db.search_all()."""
        with repo_session() as s:
            nid = None
            if novel_name:
                nid = self._get_novel_id(s, novel_name)
                if not nid:
                    return {"chapters": [], "outlines": [], "reviews": []}

            like = f"%{query}%"
            results = {"chapters": [], "outlines": [], "reviews": []}

            # Chapters
            ch_q = s.query(Chapter, Novel.name).join(Novel)
            if nid:
                ch_q = ch_q.filter(Chapter.novel_id == nid)
            ch_rows = ch_q.filter(Chapter.content.like(like))\
                         .order_by(Chapter.volume, Chapter.chapter_num).limit(limit).all()
            for ch, nname in ch_rows:
                results["chapters"].append({
                    "chapter_ref": ch.chapter_ref, "title": ch.title,
                    "word_count": ch.word_count, "volume": ch.volume,
                    "novel_name": nname,
                })

            # Outlines
            ol_q = s.query(Outline, Novel.name).join(Novel)
            if nid:
                ol_q = ol_q.filter(Outline.novel_id == nid)
            ol_rows = ol_q.filter(Outline.content.like(like)).limit(limit).all()
            for ol, nname in ol_rows:
                results["outlines"].append({"volume": ol.volume, "novel_name": nname})

            # Reviews
            rv_q = s.query(Review, Novel.name).join(Novel)
            if nid:
                rv_q = rv_q.filter(Review.novel_id == nid)
            rv_rows = rv_q.filter(
                or_(Review.ai_review.like(like), Review.script_detail.like(like))
            ).limit(limit).all()
            for rv, nname in rv_rows:
                results["reviews"].append({
                    "chapter_ref": rv.chapter_ref, "novel_name": nname,
                    "word_count": rv.word_count,
                })

            return results

    # ═══════════════════════════════════════════════════════════════
    # Config DB: DeepSeekConfig
    # ═══════════════════════════════════════════════════════════════

    def get_config(self, key: str) -> Optional[str]:
        with repo_session() as s:
            row = s.query(DeepSeekConfig).filter(DeepSeekConfig.config_key == key).first()
            return row.config_value if row else None

    def set_config(self, key: str, value: str):
        with repo_session() as s:
            row = s.query(DeepSeekConfig).filter(DeepSeekConfig.config_key == key).first()
            if row:
                row.config_value = value
                row.updated_at = _now()
            else:
                s.add(DeepSeekConfig(config_key=key, config_value=value, updated_at=_now()))

    def load_all_config(self) -> Dict[str, str]:
        """Load all config entries as a dict (for get_active_deepseek_config)."""
        with repo_session() as s:
            rows = s.query(DeepSeekConfig).all()
            return {r.config_key: r.config_value for r in rows}

    # ═══════════════════════════════════════════════════════════════
    # Config DB: BannedWord
    # ═══════════════════════════════════════════════════════════════

    def list_banned_words(self) -> List[Dict]:
        with repo_session() as s:
            return _rows_to_dicts(s.query(BannedWord).all())

    # ═══════════════════════════════════════════════════════════════
    # Config DB: ComplianceRule
    # ═══════════════════════════════════════════════════════════════

    def list_compliance_rules(self) -> List[Dict]:
        with repo_session() as s:
            return _rows_to_dicts(s.query(ComplianceRule).all())

    # ═══════════════════════════════════════════════════════════════
    # Config DB: StylePreset
    # ═══════════════════════════════════════════════════════════════

    def list_style_presets(self) -> List[Dict]:
        with repo_session() as s:
            return _rows_to_dicts(s.query(StylePreset).all())

    def get_style_preset_by_name(self, name: str) -> Optional[Dict]:
        """Look up a single style preset by name. Returns None if not found.

        Used by context_builder to resolve frontend style strings like
        "辰东风" → the actual prompt content stored in style_presets.prompt.
        """
        with repo_session() as s:
            row = s.query(StylePreset).filter(StylePreset.name == name).first()
            return _row_to_dict(row) if row else None

    # ═══════════════════════════════════════════════════════════════
    # Usage DB
    # ═══════════════════════════════════════════════════════════════

    def log_usage(self, model: str, operation: str, prompt_tokens: int = 0,
                  completion_tokens: int = 0, novel: str = "", cost: float = 0.0) -> Optional[int]:
        total = prompt_tokens + completion_tokens
        with repo_session() as s:
            ur = UsageRecord(model=model, operation=operation, novel=novel,
                           prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                           total_tokens=total, cost_estimate=cost, created_at=_now())
            s.add(ur)
            s.flush()
            return ur.id

    def upsert_daily_stats(self, model: str, operation: str, prompt_tokens: int,
                           completion_tokens: int, cost: float):
        from datetime import date
        import json as _json

        today = date.today().isoformat()
        total = prompt_tokens + completion_tokens

        with repo_session() as s:
            row = s.query(DailyStat).filter(DailyStat.date == today).first()
            if row:
                row.total_calls += 1
                row.total_prompt_tokens += prompt_tokens
                row.total_completion_tokens += completion_tokens
                row.total_tokens += total
                row.total_cost = round(row.total_cost + cost, 8)

                ops = _json.loads(row.by_operation or "{}")
                models = _json.loads(row.by_model or "{}")

                op_entry = ops.get(operation, {"calls": 0, "tokens": 0, "cost": 0.0})
                op_entry["calls"] += 1
                op_entry["tokens"] += total
                op_entry["cost"] = round(op_entry["cost"] + cost, 8)
                ops[operation] = op_entry

                md_entry = models.get(model, {"calls": 0, "tokens": 0, "cost": 0.0})
                md_entry["calls"] += 1
                md_entry["tokens"] += total
                md_entry["cost"] = round(md_entry["cost"] + cost, 8)
                models[model] = md_entry

                row.by_operation = _json.dumps(ops, ensure_ascii=False)
                row.by_model = _json.dumps(models, ensure_ascii=False)
                row.updated_at = _now()
            else:
                op_json = _json.dumps({
                    operation: {"calls": 1, "tokens": total, "cost": cost}
                }, ensure_ascii=False)
                md_json = _json.dumps({
                    model: {"calls": 1, "tokens": total, "cost": cost}
                }, ensure_ascii=False)
                ds = DailyStat(date=today, total_calls=1,
                              total_prompt_tokens=prompt_tokens,
                              total_completion_tokens=completion_tokens,
                              total_tokens=total, total_cost=cost,
                              by_operation=op_json, by_model=md_json,
                              updated_at=_now())
                s.add(ds)

    def get_usage_stats(self, days: int = 30) -> List[Dict]:
        with repo_session() as s:
            rows = s.query(DailyStat).order_by(DailyStat.date.desc()).limit(days).all()
            return _rows_to_dicts(rows)

    def get_total_usage(self) -> Dict:
        with repo_session() as s:
            result = s.query(
                func.count(UsageRecord.id).label("total_calls"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                func.sum(UsageRecord.cost_estimate).label("total_cost"),
            ).first()
            return {
                "total_calls": result[0] or 0,
                "total_tokens": result[1] or 0,
                "total_cost": round(result[2] or 0.0, 6),
            }

    def list_recent_usage(self, limit: int = 50) -> List[Dict]:
        with repo_session() as s:
            rows = s.query(UsageRecord).order_by(UsageRecord.created_at.desc()).limit(limit).all()
            return _rows_to_dicts(rows)

    # ═══════════════════════════════════════════════════════════════
    # Stats / Aggregation
    # ═══════════════════════════════════════════════════════════════

    def get_novel_stats(self, novel_name: str) -> Optional[Dict]:
        """Get aggregate stats for a novel (word counts, review counts, etc)."""
        with repo_session() as s:
            novel = s.query(Novel).filter(Novel.name == novel_name).first()
            if not novel:
                return None
            nid = novel.id
            total_chapters = s.query(func.count(Chapter.id)).filter(Chapter.novel_id == nid).scalar() or 0
            total_words = s.query(func.sum(Chapter.word_count)).filter(Chapter.novel_id == nid).scalar() or 0
            total_reviews = s.query(func.count(Review.id)).filter(Review.novel_id == nid).scalar() or 0
            total_outlines = s.query(func.count(Outline.id)).filter(Outline.novel_id == nid).scalar() or 0

            # Update novel totals
            novel.total_chapters = total_chapters
            novel.total_words = total_words
            s.flush()

            # Recent chapters
            recent = s.query(Chapter).filter(Chapter.novel_id == nid)\
                .order_by(Chapter.chapter_num.desc()).limit(20).all()
            recent_list = []
            for c in reversed(recent):
                recent_list.append({
                    "chapter_ref": c.chapter_ref,
                    "word_count": c.word_count,
                    "created_at": c.created_at,
                })

            return {
                **{c.key: getattr(novel, c.key) for c in novel.__table__.columns
                   if c.key not in ("_sa_instance_state",)},
                "total_chapters": total_chapters,
                "total_words": total_words,
                "total_reviews": total_reviews,
                "total_outlines": total_outlines,
                "recent_chapters": recent_list,
            }

    def get_usage_breakdown(self, days: int = 30) -> Dict:
        """Get detailed usage breakdown by model and operation."""
        total = self.get_total_usage()
        with repo_session() as s:
            # By model
            model_rows = s.query(
                UsageRecord.model,
                func.count(UsageRecord.id).label("calls"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
            ).group_by(UsageRecord.model).all()
            by_model = {r[0]: {"calls": r[1], "tokens": r[2] or 0} for r in model_rows}

            # By operation
            op_rows = s.query(
                UsageRecord.operation,
                func.count(UsageRecord.id).label("calls"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
            ).group_by(UsageRecord.operation).all()
            by_operation = {r[0]: {"calls": r[1], "tokens": r[2] or 0} for r in op_rows}

        return {
            "total": total,
            "by_model": by_model,
            "by_operation": by_operation,
        }

    # ═══════════════════════════════════════════════════════════════
    # Config CRUD: BannedWords
    # ═══════════════════════════════════════════════════════════════

    def add_banned_word(self, word: str, category: str = "通用",
                        replacement: str = "", severity: str = "error") -> Optional[int]:
        with repo_session() as s:
            bw = BannedWord(word=word, category=category, replacement=replacement,
                           severity=severity, created_at=_now())
            s.add(bw)
            s.flush()
            return bw.id

    def _update_config_row(self, model, rid: int, **kwargs) -> bool:
        with repo_session() as s:
            row = s.query(model).filter(model.id == rid).first()
            if not row:
                return False
            for k, v in kwargs.items():
                if hasattr(model, k):
                    setattr(row, k, v)
            if hasattr(model, "updated_at"):
                row.updated_at = _now()
            return True

    def update_banned_word(self, bid: int, **kwargs) -> bool:
        allowed = {"word", "category", "replacement", "severity"}
        return self._update_config_row(BannedWord, bid, **{k: v for k, v in kwargs.items() if k in allowed})

    def delete_banned_word(self, bid: int):
        with repo_session() as s:
            s.query(BannedWord).filter(BannedWord.id == bid).delete()

    def add_compliance_rule(self, rule_key: str, rule_value: str,
                            description: str = "", category: str = "general") -> Optional[int]:
        with repo_session() as s:
            cr = ComplianceRule(rule_key=rule_key, rule_value=rule_value,
                               description=description, category=category, updated_at=_now())
            s.add(cr)
            s.flush()
            return cr.id

    def update_compliance_rule(self, rid: int, **kwargs) -> bool:
        allowed = {"rule_key", "rule_value", "description", "category"}
        return self._update_config_row(ComplianceRule, rid, **{k: v for k, v in kwargs.items() if k in allowed})

    def delete_compliance_rule(self, rid: int):
        with repo_session() as s:
            s.query(ComplianceRule).filter(ComplianceRule.id == rid).delete()

    def add_style_preset(self, name: str, description: str = "",
                         prompt: str = "", is_active: int = 1) -> Optional[int]:
        with repo_session() as s:
            sp = StylePreset(name=name, description=description, prompt=prompt,
                            is_active=is_active, created_at=_now())
            s.add(sp)
            s.flush()
            return sp.id

    def update_style_preset(self, sid: int, **kwargs) -> bool:
        allowed = {"name", "description", "prompt", "is_active"}
        return self._update_config_row(StylePreset, sid, **{k: v for k, v in kwargs.items() if k in allowed})

    def delete_style_preset(self, sid: int):
        with repo_session() as s:
            s.query(StylePreset).filter(StylePreset.id == sid).delete()

    def list_alias_registry(self) -> List[Dict]:
        with repo_session() as s:
            return _rows_to_dicts(s.query(AliasRegistry).all())

    def add_alias_registry(self, real_name: str, alias: str,
                           category: str = "地名", notes: str = "") -> Optional[int]:
        with repo_session() as s:
            ar = AliasRegistry(real_name=real_name, alias=alias,
                              category=category, notes=notes, created_at=_now())
            s.add(ar)
            s.flush()
            return ar.id

    def update_alias_registry(self, aid: int, **kwargs) -> bool:
        allowed = {"real_name", "alias", "category", "notes"}
        return self._update_config_row(AliasRegistry, aid, **{k: v for k, v in kwargs.items() if k in allowed})

    def delete_alias_registry(self, aid: int):
        with repo_session() as s:
            s.query(AliasRegistry).filter(AliasRegistry.id == aid).delete()

    def upsert_danger_issue(self, novel_name: str, volume: str,
                            chapter_num: int, content: str) -> Dict:
        with repo_session() as s:
            nid = self._get_novel_id(s, novel_name)
            if not nid:
                return {}
            di = s.query(DangerIssue).filter(
                DangerIssue.novel_id == nid,
                DangerIssue.volume == volume,
                DangerIssue.chapter_num == chapter_num,
            ).first()
            if di:
                di.content = content
            else:
                di = DangerIssue(novel_id=nid, volume=volume,
                                 chapter_num=chapter_num, content=content,
                                 created_at=_now())
                s.add(di)
            s.flush()
            return _row_to_dict(di)

    # ═══════════════════════════════════════════════════════════════
    # Init / Bootstrap
    # ═══════════════════════════════════════════════════════════════

    def init_config_seed(self):
        """Seed config tables with default data (idempotent)."""
        banned = [
            ("中国","国家","夏国","error"), ("美国","国家","鹰国","error"),
            ("日本","国家","樱国","error"), ("英国","国家","雾都联邦","error"),
            ("法国","国家","鸢尾联邦","error"), ("德国","国家","铁十字联邦","error"),
            ("俄罗斯","国家","雪原联邦","error"), ("韩国","国家","槿国","error"),
            ("北京","城市","上京","error"), ("上海","城市","海州","error"),
            ("深圳","城市","鹏都","error"), ("广州","城市","南陵","error"),
            ("成都","城市","锦都","error"), ("重庆","城市","山城","error"),
            ("微信","产品","信聊","warn"), ("支付宝","产品","金付","warn"),
            ("淘宝","产品","万货","warn"), ("百度","产品","千寻","warn"),
            ("抖音","产品","律动","warn"), ("微博","产品","言博","warn"),
        ]
        rules = [
            ("world_name","蓝星","虚构世界名称","世界观"),
            ("naming_rule","所有地名、人名、组织名、产品名必须使用虚构名称","禁止使用真实世界名称","规则"),
            ("bypass_rule","不得使用谐音、缩写、拼音、外文原名绕过规则","杜绝擦边绕过","规则"),
            ("chapter_min_words","2500","章节最低字数要求","写作规范"),
        ]
        styles = [
            ("金庸风","传统武侠，典雅大气","以金庸风格写作：典雅大气的文风，注重人物性格刻画和意境描写，多用传统修辞手法，节奏张弛有度。"),
            ("古龙风","简洁凌厉，意境留白","以古龙风格写作：短句快节奏，对话为主体，大量留白和意境描写，人物神秘感强。"),
            ("番茄风","爽文直白，快节奏","以番茄风格写作：直白爽快的文风，快节奏推进剧情，注重升级体系和战斗描写。"),
            ("辰东风","宏大叙事，神话底蕴","以辰东风格写作：宏大的世界观设定，厚重的神话底蕴，伏笔深远，人物有血有肉。"),
            ("默认","项目基线风格","以流畅自然的中文写作，注重情节推进和人物塑造，文风平实有力。"),
        ]

        with repo_session() as s:
            # Banned words
            for word, cat, repl, sev in banned:
                if not s.query(BannedWord).filter(BannedWord.word == word).first():
                    s.add(BannedWord(word=word, category=cat, replacement=repl, severity=sev,
                                     created_at=_now()))

            # Compliance rules
            for rkey, rval, desc, cat in rules:
                if not s.query(ComplianceRule).filter(ComplianceRule.rule_key == rkey).first():
                    s.add(ComplianceRule(rule_key=rkey, rule_value=rval, description=desc,
                                        category=cat, updated_at=_now()))

            # Style presets
            for sn, sd, sp in styles:
                if not s.query(StylePreset).filter(StylePreset.name == sn).first():
                    s.add(StylePreset(name=sn, description=sd, prompt=sp,
                                     is_active=1, created_at=_now()))


# ── Singleton ────────────────────────────────────────────────────────────

_repo: Optional[Repository] = None


def get_repo() -> Repository:
    """Get or create the Repository singleton."""
    global _repo
    if _repo is None:
        _repo = Repository()
    return _repo


# ── Convenience functions ────────────────────────────────────────────────

def get_session() -> Generator[Session, None, None]:
    """Convenience: get a raw SQLAlchemy session (for complex queries)."""
    from db import get_session_factory
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_tables():
    """Create all tables if they don't exist. Call on startup."""
    from db import get_engine
    engine = get_engine()
    Base.metadata.create_all(engine)
