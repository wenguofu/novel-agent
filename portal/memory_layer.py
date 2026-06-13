"""
Memory Layer — Multi-strategy RAG retrieval for novel writing continuity.

Problem: After 100k+ words, the agent forgets what happened before.
Solution: Multi-query semantic search against the ChromaDB vector index,
          structured by retrieval strategy.

Strategies:
  1. PLOT_CONTINUITY  — What happened recently that needs continuation?
  2. CHARACTER_STATE  — What is each character's current state/arc position?
  3. WORLD_EVOLUTION  — What world elements changed? New locations? Rules?
  4. FORESHADOWING    — What foreshadowing is still unresolved?
  5. SIMILAR_SCENES   — Have we written similar scenes before?
  6. RECENT_EVENTS    — What happened in the last N chapters?
"""

import re
import time
import threading
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

# Import the existing RAG engine (lazy — won't trigger model download)
from rag_engine import query_categories as _rag_query, _is_chroma_available
from token_utils import count_tokens


@dataclass
class MemoryResult:
    """A single memory retrieval result."""
    content: str
    score: float
    source: str
    file_type: str
    volume: Optional[int] = None
    chapter: Optional[int] = None
    title: str = ""
    characters: List[str] = field(default_factory=list)
    char_count: int = 0


@dataclass
class MemoryQueryResult:
    """Aggregated results from a memory query."""
    strategy: str
    query_text: str
    results: List[MemoryResult]
    tokens_used: int
    tokens_budget: int


# ── Query Strategy Definitions ──────────────────────────────────────────

class MemoryStrategies:
    """Pre-defined query strategies for different types of memory retrieval."""

    @staticmethod
    def plot_continuity(volume: int, chapter_num: int) -> str:
        """What plot threads are active and need continuation?"""
        return (
            f"第{volume}卷第{chapter_num}章 前情提要 剧情发展 关键事件 "
            f"矛盾冲突 转折 伏笔推进 角色目标 当前困境 危机"
        )

    @staticmethod
    def character_state(char_names: List[str], volume: int) -> str:
        """What is the current state of each character?"""
        names_str = " ".join(char_names[:8])
        return (
            f"{names_str} 当前状态 所在地点 目标变化 情感变化 "
            f"能力提升 关系发展 性格演变 第{volume}卷 最新进展"
        )

    @staticmethod
    def world_evolution(volume: int) -> str:
        """What world elements have changed or been introduced?"""
        return (
            f"第{volume}卷 世界观 新地点 新规则 新势力 新设定 "
            f"地图变化 力量体系 组织变动 环境改变 秘宝 禁地"
        )

    @staticmethod
    def foreshadowing_status(volume: int) -> str:
        """What foreshadowing is still unresolved?"""
        return (
            f"伏笔 未回收 未揭示 秘密 真相 隐藏 铺垫 暗示 "
            f"第{volume}卷 待填坑 线索 谜团"
        )

    @staticmethod
    def similar_scenes(outline_section: str, volume: int) -> str:
        """Have we written similar scenes before that should be referenced?"""
        # Use the current chapter's outline to find similar past scenes
        base = outline_section[:200] if outline_section else f"第{volume}卷"
        return f"类似场景 相似事件 {base} 前文呼应 历史事件"

    @staticmethod
    def recent_events(volume: int, chapter_num: int, lookback: int = 5) -> str:
        """What happened in the last N chapters?"""
        start_ch = max(1, chapter_num - lookback)
        return (
            f"第{volume}卷第{start_ch}章到第{chapter_num}章 内容摘要 "
            f"发生了什么 关键转折 新角色 新地点 重要对话 情感高潮"
        )

    @staticmethod
    def character_arc_progress(char_name: str, volume: int) -> str:
        """Track a specific character's arc across the whole novel."""
        return (
            f"{char_name} 成长弧线 性格变化 能力成长 关系演变 "
            f"重要经历 关键决策 信念转变 身份变化 第1卷到第{volume}卷"
        )


# ── Memory Layer ────────────────────────────────────────────────────────

class MemoryLayer:
    """Multi-strategy RAG memory retrieval for novel writing.

    Usage:
        ml = MemoryLayer()
        memory = ml.retrieve(
            novel_name="我的小说",
            volume=5,
            chapter_num=75,
            character_names=["主角", "女主", "反派"],
            total_token_budget=3000,
        )
        # memory.context_text -> formatted string for prompt injection
        # memory.results -> list of MemoryQueryResult for debugging
    """

    _instance: Optional["MemoryLayer"] = None

    def __init__(self):
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = 120.0  # 2 min TTL for memory (longer than context)
        self._cache_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MemoryLayer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def retrieve(
        self,
        novel_name: str,
        volume: int,
        chapter_num: int,
        character_names: Optional[List[str]] = None,
        outline_section: str = "",
        total_token_budget: int = 3000,
        strategies: Optional[List[str]] = None,
    ) -> "MemoryContext":
        """Execute multi-strategy memory retrieval.

        Args:
            novel_name: Novel project name
            volume: Current volume number
            chapter_num: Current chapter number
            character_names: List of character names for state queries
            outline_section: Current chapter's outline (for similar scene matching)
            total_token_budget: Max tokens for all memory results combined
            strategies: List of strategy names to use (default: all)

        Returns:
            MemoryContext with formatted text and structured results
        """
        character_names = character_names or []
        if strategies is None:
            strategies = [
                "plot_continuity",
                "character_state",
                "world_evolution",
                "foreshadowing_status",
                "recent_events",
            ]

        # Check cache
        cache_key = f"{novel_name}|{volume}|{chapter_num}|{','.join(sorted(character_names[:5]))}"
        now = time.time()
        with self._cache_lock:
            if cache_key in self._cache:
                ts, result = self._cache[cache_key]
                if now - ts < self._cache_ttl:
                    return result

        # Build query categories
        categories = []
        strategy_budgets = self._allocate_budgets(strategies, total_token_budget)

        for strategy in strategies:
            budget = strategy_budgets.get(strategy, 300)
            query_text = self._build_query(strategy, volume, chapter_num,
                                           character_names, outline_section)
            if query_text:
                categories.append({
                    "category": strategy,
                    "query": query_text,
                    "max_tokens": budget,
                    "file_type": self._file_type_for_strategy(strategy),
                    "limit": self._limit_for_strategy(strategy),
                    "volume": volume,
                    "chapter": chapter_num,
                })

        # Execute queries via rag_engine (which handles ChromaDB fallback)
        if _is_chroma_available():
            raw_results = _rag_query(novel_name, categories, total_token_budget)
        else:
            raw_results = self._fallback_db_retrieval(novel_name, categories)

        # Parse results
        query_results = []
        for cat_result in raw_results.get("results", []):
            strategy_name = cat_result.get("category", "unknown")
            chunks = []
            for chunk in cat_result.get("chunks", []):
                chunks.append(MemoryResult(
                    content=chunk.get("content", ""),
                    score=chunk.get("score", 0.0),
                    source=chunk.get("source", ""),
                    file_type=chunk.get("file_type", ""),
                    volume=chunk.get("volume"),
                    chapter=chunk.get("chapter"),
                    title=chunk.get("title", ""),
                    characters=chunk.get("characters", []),
                    char_count=chunk.get("char_count", 0),
                ))
            query_results.append(MemoryQueryResult(
                strategy=strategy_name,
                query_text=self._build_query(strategy_name, volume, chapter_num,
                                             character_names, outline_section),
                results=chunks,
                tokens_used=cat_result.get("tokens_used", 0),
                tokens_budget=cat_result.get("tokens_requested", 0),
            ))

        context = MemoryContext(
            novel_name=novel_name,
            volume=volume,
            chapter_num=chapter_num,
            query_results=query_results,
            total_tokens=raw_results.get("total_tokens", 0),
            token_budget=total_token_budget,
        )

        # Cache
        with self._cache_lock:
            self._cache[cache_key] = (now, context)
            # Prune old entries
            if len(self._cache) > 50:
                oldest = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest]

        return context

    def _build_query(self, strategy: str, volume: int, chapter_num: int,
                     character_names: List[str], outline: str) -> str:
        """Build the query text for a given strategy."""
        handlers = {
            "plot_continuity": lambda: MemoryStrategies.plot_continuity(volume, chapter_num),
            "character_state": lambda: MemoryStrategies.character_state(character_names, volume),
            "world_evolution": lambda: MemoryStrategies.world_evolution(volume),
            "foreshadowing_status": lambda: MemoryStrategies.foreshadowing_status(volume),
            "similar_scenes": lambda: MemoryStrategies.similar_scenes(outline, volume),
            "recent_events": lambda: MemoryStrategies.recent_events(volume, chapter_num),
        }
        handler = handlers.get(strategy)
        return handler() if handler else ""

    def _file_type_for_strategy(self, strategy: str) -> Optional[str]:
        """Map strategy to ChromaDB file_type filter."""
        mapping = {
            "plot_continuity": "chapter",
            "character_state": "chapter",
            "world_evolution": "world_building",
            "foreshadowing_status": "plot_arc",
            "similar_scenes": "chapter",
            "recent_events": "chapter",
            "character_arc": "chapter",
        }
        return mapping.get(strategy)

    def _limit_for_strategy(self, strategy: str) -> int:
        """Number of chunks to retrieve per strategy."""
        return {
            "plot_continuity": 8,
            "character_state": 6,
            "world_evolution": 5,
            "foreshadowing_status": 5,
            "similar_scenes": 5,
            "recent_events": 5,
            "character_arc": 5,
        }.get(strategy, 5)

    def _allocate_budgets(self, strategies: List[str],
                          total_budget: int) -> Dict[str, int]:
        """Allocate token budgets across strategies."""
        weights = {
            "plot_continuity": 0.28,
            "character_state": 0.22,
            "world_evolution": 0.15,
            "foreshadowing_status": 0.15,
            "recent_events": 0.12,
            "similar_scenes": 0.08,
        }
        budgets = {}
        for s in strategies:
            budgets[s] = int(total_budget * weights.get(s, 0.1))
        return budgets

    def _fallback_db_retrieval(self, novel_name: str,
                               categories: List[dict]) -> dict:
        """Fallback retrieval via repository LIKE search.

        Used when ChromaDB is unavailable. The fallback goes through
        ``content_db.search_all`` → ``repository.get_repo().search_*``
        which uses LIKE-based substring matching against MySQL.
        """
        import content_db as db

        results = []
        total_tokens = 0
        for cat in categories:
            query = cat.get("query", "")
            limit = cat.get("limit", 5)
            max_tok = cat.get("max_tokens", 500)
            file_type = cat.get("file_type")

            # Use content_db's FTS search
            search_results = db.search_all(query, novel_name=novel_name, limit=limit)

            chunks = []
            tokens_used = 0
            # Collect from chapters
            for r in search_results.get("chapters", []):
                content = r.get("snippet", "")[:800]
                est_tok = count_tokens(content)
                if tokens_used + est_tok > max_tok:
                    break
                chunks.append({
                    "content": content,
                    "score": 0.5,  # FTS doesn't provide scores
                    "source": r.get("chapter_ref", ""),
                    "file_type": "chapter",
                })
                tokens_used += est_tok

            # Collect from outlines
            if tokens_used < max_tok:
                for r in search_results.get("outlines", []):
                    content = r.get("snippet", "")[:500]
                    est_tok = count_tokens(content)
                    if tokens_used + est_tok > max_tok:
                        break
                    chunks.append({
                        "content": content,
                        "score": 0.4,
                        "source": r.get("volume", ""),
                        "file_type": "outline",
                    })
                    tokens_used += est_tok

            results.append({
                "category": cat["category"],
                "chunks": chunks,
                "tokens_used": tokens_used,
                "tokens_requested": max_tok,
            })
            total_tokens += tokens_used

        return {
            "results": results,
            "total_tokens": total_tokens,
            "max_tokens": sum(c.get("max_tokens", 500) for c in categories),
            "mode": "db-fts5-fallback",
        }

    def clear_cache(self):
        """Clear the memory retrieval cache."""
        with self._cache_lock:
            self._cache.clear()


# ── Memory Context (formatted output) ───────────────────────────────────

@dataclass
class MemoryContext:
    """Structured memory retrieval results with formatted text output."""
    novel_name: str
    volume: int
    chapter_num: int
    query_results: List[MemoryQueryResult]
    total_tokens: int
    token_budget: int

    @property
    def context_text(self) -> str:
        """Format memory results as a structured prompt section.

        Designed to be injected into the system prompt for chapter generation.
        """
        if not self.query_results or all(not qr.results for qr in self.query_results):
            return ""

        sections = ["## 📚 长期记忆检索（RAG 语义搜索）"]
        sections.append(f"以下是从全书记忆库中检索到的最相关内容 "
                       f"(共 {self._total_chunks()} 个片段, "
                       f"≤{self.token_budget} tokens):\n")

        strategy_labels = {
            "plot_continuity": "📖 剧情连续性",
            "character_state": "👤 角色最新状态",
            "world_evolution": "🌍 世界观演变",
            "foreshadowing_status": "🔮 待回收伏笔",
            "similar_scenes": "🔄 相似场景参考",
            "recent_events": "📝 近期事件摘要",
            "character_arc": "📈 角色成长弧线",
        }

        chunk_idx = 0
        for qr in self.query_results:
            if not qr.results:
                continue

            label = strategy_labels.get(qr.strategy, qr.strategy)
            sections.append(f"\n### {label} ({len(qr.results)} 片段)")

            for r in qr.results:
                chunk_idx += 1
                # Build metadata line
                meta_parts = []
                if r.volume:
                    meta_parts.append(f"卷{r.volume}")
                if r.chapter:
                    meta_parts.append(f"ch-{r.chapter:04d}" if r.chapter >= 1000 else f"ch-{r.chapter:03d}")
                if r.characters:
                    meta_parts.append(f"角色: {', '.join(r.characters[:3])}")
                meta_str = " | ".join(meta_parts) if meta_parts else ""

                # Truncate content for readability
                content = r.content
                if len(content) > 600:
                    content = content[:600] + "..."

                sections.append(
                    f"\n**[{chunk_idx}] {r.file_type}** "
                    f"匹配度:{r.score:.2f}"
                    + (f" | {meta_str}" if meta_str else "") +
                    f"\n```\n{content}\n```"
                )

        sections.append("\n---")
        sections.append("**使用说明**: 以上内容由语义搜索自动从全书记忆库中检索。")
        sections.append("请优先参考其中的角色状态变化、未回收伏笔、世界观规则和近期剧情发展。")
        sections.append("如有矛盾，以正式设定文件 (characters.md, world_bible.md) 为准。")

        return "\n".join(sections)

    @property
    def is_empty(self) -> bool:
        return self._total_chunks() == 0

    def _total_chunks(self) -> int:
        return sum(len(qr.results) for qr in self.query_results)

    def to_dict(self) -> dict:
        """Convert to dict for API responses / debugging."""
        return {
            "novel": self.novel_name,
            "volume": self.volume,
            "chapter": self.chapter_num,
            "total_tokens": self.total_tokens,
            "token_budget": self.token_budget,
            "total_chunks": self._total_chunks(),
            "strategies": [
                {
                    "name": qr.strategy,
                    "chunks": len(qr.results),
                    "tokens_used": qr.tokens_used,
                    "top_score": max((r.score for r in qr.results), default=0),
                }
                for qr in self.query_results
            ],
        }


# ── Convenience function ────────────────────────────────────────────────

_ml: Optional[MemoryLayer] = None


def get_memory_layer() -> MemoryLayer:
    global _ml
    if _ml is None:
        _ml = MemoryLayer()
    return _ml


def retrieve_memory(
    novel_name: str,
    volume: int,
    chapter_num: int,
    character_names: Optional[List[str]] = None,
    outline_section: str = "",
    total_token_budget: int = 3000,
) -> MemoryContext:
    """Convenience function: retrieve long-term memory for a chapter."""
    return get_memory_layer().retrieve(
        novel_name=novel_name,
        volume=volume,
        chapter_num=chapter_num,
        character_names=character_names,
        outline_section=outline_section,
        total_token_budget=total_token_budget,
    )
