"""
Prompt Manager — Jinja2-based template engine for system prompts.

Replaces hardcoded Python string prompts with version-controlled Jinja2 templates.
Features:
  - Template loading from prompts/ directory
  - LRU caching with TTL
  - Pydantic validation of template variables
  - Fallback to defaults when templates are missing
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, ValidationError

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ── Template variable schemas ──────────────────────────────────────────

class CoreInstructionsVars(BaseModel):
    """No variables needed for core instructions."""
    pass


class CreateNovelUserVars(BaseModel):
    genre: str = ""
    protagonist: str = ""
    selling_point: str = ""
    word_goal: str = "100万"
    perspective: str = "第三人称"
    references: str = ""


class ChapterFooterVars(BaseModel):
    volume: int
    chapter_num: int
    style: str = ""
    instructions: str = ""


class ReviewSystemVars(BaseModel):
    """No variables needed for review system prompt."""
    pass


# ── Prompt Manager ──────────────────────────────────────────────────────

# Schema map for template variable validation
_SCHEMA_MAP: Dict[str, type] = {
    "core_instructions": CoreInstructionsVars,
    "create_novel_user": CreateNovelUserVars,
    "chapter_context_footer": ChapterFooterVars,
    "review_system": ReviewSystemVars,
}


class PromptManager:
    """Loads, caches, and renders Jinja2 prompt templates.

    Usage:
        pm = PromptManager()
        prompt = pm.render("core_instructions")
        prompt = pm.render("create_novel_user", {"genre": "玄幻", ...})
    """

    _instance: Optional["PromptManager"] = None

    def __init__(self, prompts_dir: Optional[Path] = None):
        self._prompts_dir = Path(prompts_dir or PROMPTS_DIR)
        self._cache: Dict[str, tuple[float, str]] = {}  # key -> (timestamp, rendered)
        self._cache_ttl: float = 300.0  # 5 minutes for static prompts
        self._env: Optional[Environment] = None
        self._init_env()

    def _init_env(self):
        """Initialize Jinja2 environment with fallback for missing directory."""
        if self._prompts_dir.exists():
            self._env = Environment(
                loader=FileSystemLoader(str(self._prompts_dir)),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        else:
            self._env = None

    @classmethod
    def get_instance(cls) -> "PromptManager":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def render(self, template_name: str, variables: Optional[Dict[str, Any]] = None,
               cache: bool = True) -> str:
        """Render a prompt template with optional variable injection.

        Args:
            template_name: Template file name without .j2 extension
            variables: Dict of template variables (validated against schema)
            cache: Whether to cache the rendered result

        Returns:
            Rendered prompt string, or empty string on failure

        Raises:
            ValueError: If template variables fail validation
        """
        variables = variables or {}

        # Validate variables against schema if one exists
        schema_cls = _SCHEMA_MAP.get(template_name)
        if schema_cls:
            try:
                schema_cls(**variables)
            except ValidationError as e:
                raise ValueError(f"Template '{template_name}' variable validation failed: {e}")

        # Check cache for parameterless renders
        cache_key = f"{template_name}:{_quick_hash(variables)}" if variables else template_name
        if cache:
            now = time.time()
            if cache_key in self._cache:
                ts, result = self._cache[cache_key]
                if now - ts < self._cache_ttl:
                    return result

        # Try Jinja2 template
        result = self._render_jinja2(template_name, variables)

        # Fallback: try static file read
        if result is None:
            result = self._read_static(template_name) or ""

        # Cache if successful
        if cache and result:
            self._cache[cache_key] = (time.time(), result)

        return result

    def _render_jinja2(self, name: str, variables: Dict[str, Any]) -> Optional[str]:
        """Render via Jinja2. Returns None if template not found."""
        if self._env is None:
            return None
        try:
            template = self._env.get_template(f"{name}.j2")
            return template.render(**variables)
        except TemplateNotFound:
            return None
        except Exception as e:
            # Log and return empty
            import logging
            logging.warning(f"[PromptManager] Render error for '{name}': {e}")
            return None

    def _read_static(self, name: str) -> Optional[str]:
        """Fallback: read template as static .md file."""
        for ext in (".md", ".txt"):
            fpath = self._prompts_dir / f"{name}{ext}"
            if fpath.exists():
                return fpath.read_text(encoding="utf-8")
        return None

    def render_or_default(self, template_name: str, default: str,
                          variables: Optional[Dict[str, Any]] = None) -> str:
        """Render template, return default if rendering fails."""
        result = self.render(template_name, variables, cache=False)
        return result if result else default

    def clear_cache(self):
        """Clear the template cache."""
        self._cache.clear()

    def list_templates(self) -> list:
        """List available template names."""
        if not self._prompts_dir.exists():
            return []
        templates = []
        for f in self._prompts_dir.iterdir():
            if f.suffix in (".j2", ".md", ".txt"):
                templates.append(f.stem if f.suffix == ".j2" else f.name.replace(f.suffix, ""))
        return sorted(templates)


def _quick_hash(d: Dict[str, Any]) -> str:
    """Create a quick stable hash for a small dict (for cache keys)."""
    try:
        import json
        return str(hash(json.dumps(d, sort_keys=True, default=str)))
    except Exception:
        return str(hash(str(d)))


# ── Convenience functions for use in app.py ────────────────────────────

_pm: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    global _pm
    if _pm is None:
        _pm = PromptManager()
    return _pm


def render_prompt(template_name: str, **kwargs) -> str:
    """Convenience function: render a prompt template."""
    return get_prompt_manager().render(template_name, kwargs)
