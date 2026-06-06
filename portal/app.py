"""Novel Agent Web Portal - AI写作Web Portal (MiniMax / Anthropic-compatible API)"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from functools import wraps
import logging

import httpx
from flask import Flask, jsonify, render_template, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS

try:
    import sqlite3 as _sqlite3
except ImportError:
    _sqlite3 = None  # MySQL mode — not available

from content_db import (
    get_db as get_content_db, init_db as init_content_db,
    sync_novel_from_files, sync_all_novels, search_all, get_novel_stats
)

from config import (
    DEEPSEEK_API_BASE,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEBUG,
    NOVEL_AGENT_ROOT,
    PORTAL_HOST,
    PORTAL_PORT,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
)

# Structured error handling — exception hierarchy + Flask handlers
# (defined in portal/errors.py). See harness plan item [5].
from errors import (
    register_error_handlers,
    NovelAgentError,
    APIError,
    NotFoundError,
    ValidationError,
    DatabaseError,
    ConfigError,
    RateLimitError,
    GateBlockedError,
    safe_call,
    safe_db_call,
    safe_io_call,
)

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# Register centralized error handlers (404 JSON, 405 JSON, 500 JSON,
# NovelAgentError → structured). The SPA-fallback 404 handler below
# overrides the 404 from this call so React client routes still
# resolve to index.html.
register_error_handlers(app)

# ─── Load Hermes env vars at startup ─────────────────────────────────────
_HERMES_ENV = os.path.expanduser("~/.hermes/.env")
if os.path.exists(_HERMES_ENV):
    with open(_HERMES_ENV, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                _key, _val = _key.strip(), _val.strip()
                if _val and _val != "***":  # skip redacted placeholders
                    os.environ.setdefault(_key, _val)

# ─── User Config Persistence ───────────────────────────────────────────────

DEEPSEEK_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek_config.json")

# Database paths
_PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DB_PATH = os.path.join(_PORTAL_DIR, "config.db")
CONTENT_DB_PATH = os.path.join(_PORTAL_DIR, "content.db")
USAGE_DB_PATH = os.path.join(_PORTAL_DIR, "usage.db")


# ─── Usage DB ──────────────────────────────────────────────────────────────

def _init_usage_db():
    """No-op: Tables created by ensure_unified_schema() via ORM."""
    pass

def log_token_usage(model, operation, prompt_tokens, completion_tokens, novel=""):
    """Log token usage to usage.db. Non-blocking; tracking errors are
    logged but never raised so the main flow is not blocked."""
    try:
        total_tokens = prompt_tokens + completion_tokens
        cost = _estimate_cost(model, prompt_tokens, completion_tokens)

        from repository import get_repo
        get_repo().log_usage(model, operation, prompt_tokens, completion_tokens, novel=novel, cost=cost)
    except Exception as e:
        # Tracking failure must not block the main flow, but we no
        # longer swallow silently — log so operators can see it.
        logging.warning(f"[log_token_usage] tracking failed: {e}")


def _estimate_cost(model, prompt_tokens, completion_tokens):
    """Estimate cost in USD based on model pricing.
    Supports MiniMax M2.7, DeepSeek V3/R1 pricing tiers.
    """
    model_lower = model.lower()
    if "reasoner" in model_lower or "r1" in model_lower:
        input_price = 0.14 / 1_000_000
        output_price = 0.28 / 1_000_000
    elif "minimax" in model_lower or "m2" in model_lower:
        # MiniMax M2.7 pricing (adjust if needed)
        input_price = 0.27 / 1_000_000
        output_price = 1.10 / 1_000_000
    else:
        # default / deepseek-chat / v3
        input_price = 0.27 / 1_000_000
        output_price = 1.10 / 1_000_000
    return round(prompt_tokens * input_price + completion_tokens * output_price, 6)


# Initialize usage DB on module load
_init_usage_db()


def load_user_deepseek_config():
    try:
        if os.path.exists(DEEPSEEK_CONFIG_PATH):
            with open(DEEPSEEK_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f'[load_user_deepseek_config] {e}')
    return {"api_key": "", "api_base": "", "model": "", "temperature": "", "max_tokens": "", "top_p": ""}


def save_user_deepseek_config(api_key="", api_base="", model="", temperature="", max_tokens="", top_p=""):
    data = {"api_key": api_key, "api_base": api_base, "model": model, "temperature": temperature, "max_tokens": max_tokens, "top_p": top_p}
    with open(DEEPSEEK_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def get_active_deepseek_config():
    user = load_user_deepseek_config()
    return {
        "api_key": user.get("api_key") or DEEPSEEK_API_KEY,
        "api_base": user.get("api_base") or DEEPSEEK_API_BASE,
        "model": user.get("model") or DEEPSEEK_MODEL,
        "temperature": float(user.get("temperature") or DEFAULT_TEMPERATURE),
        "max_tokens": int(user.get("max_tokens") or DEFAULT_MAX_TOKENS),
        "top_p": float(user.get("top_p") or DEFAULT_TOP_P),
        "user_configured": bool(user.get("api_key")),
    }


# ─── Helpers ────────────────────────────────────────────────────────────────


def get_agent_root():
    return os.path.join(NOVEL_AGENT_ROOT, "agent-system")


def get_novels_dir():
    return os.path.join(NOVEL_AGENT_ROOT, "novels")


def get_scripts_dir():
    return os.path.join(get_agent_root(), "scripts")


def get_templates_dir():
    return os.path.join(NOVEL_AGENT_ROOT, "templates")


def list_novels():
    novels_dir = get_novels_dir()
    if not os.path.exists(novels_dir):
        return []
    novels = []
    for d in sorted(os.listdir(novels_dir)):
        novel_path = os.path.join(novels_dir, d)
        if os.path.isdir(novel_path) and not d.startswith("."):
            novels.append(d)
    return novels


def read_novel_file(novel_name, *path_parts):
    file_path = os.path.join(get_novels_dir(), novel_name, *path_parts)
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def write_novel_file(novel_name, content, *path_parts):
    file_path = os.path.join(get_novels_dir(), novel_name, *path_parts)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def run_script(script_name, *args, cwd=None):
    script_path = os.path.join(get_scripts_dir(), script_name)
    if not os.path.exists(script_path):
        return {"success": False, "error": f"脚本不存在: {script_name}"}
    cmd = [sys.executable, script_path] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=cwd or get_agent_root()
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "脚本执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def count_words(text):
    """Count Chinese characters + English words"""
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english


def get_novel_status(novel_name):
    novel_path = os.path.join(get_novels_dir(), novel_name)
    if not os.path.exists(novel_path):
        return None

    info = {"name": novel_name, "path": novel_path}

    project = read_novel_file(novel_name, "project.md")
    if project:
        lines = project.split("\n")
        for line in lines:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().strip(" #")
                val = parts[1].strip()
                if key in ("书名", "作品名", "title", "Title"):
                    info["title"] = val
            if line.startswith("#") and "简介" in line:
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    info["summary"] = lines[idx + 1].strip().strip("# ")
                    break

    info.setdefault("title", novel_name)
    info.setdefault("summary", "")

    # Count chapters + word count
    manuscript_dir = os.path.join(novel_path, "manuscript")
    total_chapters = 0
    total_words = 0
    volumes = []
    if os.path.exists(manuscript_dir):
        for vol_dir in sorted(os.listdir(manuscript_dir)):
            vol_path = os.path.join(manuscript_dir, vol_dir)
            if os.path.isdir(vol_path) and not vol_dir.startswith('.'):
                chapter_files = sorted([f for f in os.listdir(vol_path) if f.endswith(".md")])
                chapters = []
                vol_words = 0
                for f in chapter_files:
                    ch_path = os.path.join(vol_path, f)
                    with open(ch_path, "r", encoding="utf-8") as fh:
                        ch_text = fh.read()
                    wc = count_words(ch_text)
                    vol_words += wc
                    chapters.append({"name": f.replace(".md", ""), "words": wc})
                total_chapters += len(chapters)
                total_words += vol_words
                volumes.append({
                    "name": vol_dir,
                    "chapter_count": len(chapters),
                    "chapters": chapters,
                    "total_words": vol_words,
                })

    info["total_chapters"] = total_chapters
    info["total_words"] = total_words
    info["volumes"] = volumes

    status_file = read_novel_file(novel_name, "state", "current_status.md")
    info["status_content"] = status_file or ""

    outline_dir = os.path.join(novel_path, "outline")
    outline_files = []
    if os.path.exists(outline_dir):
        for f in sorted(os.listdir(outline_dir)):
            if f.endswith("-chapters.md"):
                outline_files.append(f)
    info["outline_files"] = outline_files

    reviews_dir = os.path.join(novel_path, "reviews")
    review_count = 0
    if os.path.exists(reviews_dir):
        review_count = len([f for f in os.listdir(reviews_dir) if f.endswith(".md")])
    info["review_count"] = review_count

    # Find last generated chapter
    info["last_chapter"] = None
    if volumes:
        last_vol = volumes[-1]
        if last_vol["chapters"]:
            last_ch = last_vol["chapters"][-1]
            info["last_chapter"] = f"{last_vol['name']}/{last_ch['name']}"
            info["last_chapter_words"] = last_ch["words"]

    # Get characters info
    chars_content = read_novel_file(novel_name, "characters.md")
    info["has_characters"] = bool(chars_content)

    return info


# ─── AI API ────────────────────────────────────────────────────────────────

def _is_anthropic_api(api_base):
    """Detect if the API uses Anthropic Messages format based on URL."""
    return "/anthropic" in api_base


def _build_anthropic_payload(messages, system_prompt, model, temperature, max_tokens, top_p, stream):
    """Build Anthropic Messages API request payload."""
    payload = {
        "model": model,
        "messages": messages,  # Anthropic expects messages without system role
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    return payload


def _build_openai_payload(messages, system_prompt, model, temperature, max_tokens, top_p, stream):
    """Build OpenAI-compatible API request payload."""
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    return {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "stream": stream,
    }


def deepseek_chat(messages, system_prompt=None, temperature=None, max_tokens=None, top_p=None, stream=False, operation=None, novel=""):
    cfg = get_active_deepseek_config()
    api_key = cfg["api_key"]
    api_base = cfg["api_base"]
    model = cfg["model"]

    if not api_key:
        return {"success": False, "error": "API Key 未配置，请在设置页面中配置"}

    is_anthropic = _is_anthropic_api(api_base)

    if is_anthropic:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        endpoint = f"{api_base}/v1/messages"
        temperature_val = temperature if temperature is not None else cfg["temperature"]
        max_tokens_val = max_tokens if max_tokens is not None else cfg["max_tokens"]
        top_p_val = top_p if top_p is not None else cfg["top_p"]
        payload = _build_anthropic_payload(
            messages, system_prompt, model,
            temperature_val, max_tokens_val, top_p_val, stream,
        )
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{api_base}/chat/completions"
        temperature_val = temperature if temperature is not None else cfg["temperature"]
        max_tokens_val = max_tokens if max_tokens is not None else cfg["max_tokens"]
        top_p_val = top_p if top_p is not None else cfg["top_p"]
        payload = _build_openai_payload(
            messages, system_prompt, model,
            temperature_val, max_tokens_val, top_p_val, stream,
        )

    if not stream:
        try:
            with httpx.Client(timeout=300) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API错误 {resp.status_code}: {resp.text}",
                    }
                data = resp.json()

                if is_anthropic:
                    # Anthropic response format
                    content_blocks = data.get("content", [])
                    content = ""
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                    usage = data.get("usage", {})
                    if operation and usage:
                        log_token_usage(
                            model=model,
                            operation=operation,
                            prompt_tokens=usage.get("input_tokens", 0),
                            completion_tokens=usage.get("output_tokens", 0),
                            novel=novel,
                        )
                else:
                    # OpenAI response format
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    if operation and usage:
                        log_token_usage(
                            model=model,
                            operation=operation,
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            novel=novel,
                        )
                return {"success": True, "content": content, "usage": usage}
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        # Return the client + payload for streaming
        return {"__stream__": True, "payload": payload, "headers": headers,
                "api_base": api_base, "is_anthropic": is_anthropic, "endpoint": endpoint}


# ─── React Frontend Static Serving ──────────────────────────────────────────

_REACT_DIST = os.path.join(_PORTAL_DIR, "frontend", "dist")
_REACT_ASSETS = os.path.join(_REACT_DIST, "assets")
_HAS_REACT_BUILD = os.path.exists(_REACT_DIST) and os.path.exists(os.path.join(_REACT_DIST, "index.html"))

if _HAS_REACT_BUILD:
    @app.route("/assets/<path:filename>")
    def serve_react_assets(filename):
        return send_from_directory(_REACT_ASSETS, filename)

    # SPA fallback: serve index.html for any non-API, non-asset route.
    # For /api/* paths, return a structured JSON error using the
    # shape defined in errors.py so the SPA fallback does not lose
    # the contract documented in tests/functional/_helpers.py
    # (success=False on 404).
    @app.errorhandler(404)
    def spa_fallback(e):
        if not request.path.startswith("/api/"):
            return send_from_directory(_REACT_DIST, "index.html")
        return NotFoundError("接口不存在").to_response()

@app.route("/")
def index():
    if _HAS_REACT_BUILD:
        return send_from_directory(_REACT_DIST, "index.html")
    return render_template("index.html")


@app.route("/api/novels")
def api_list_novels():
    novels = list_novels()
    result = []
    for n in novels:
        status = get_novel_status(n)
        if status:
            result.append(status)
    return jsonify({"success": True, "novels": result})


@app.route("/api/novels/<novel_name>")
def api_novel_detail(novel_name):
    status = get_novel_status(novel_name)
    if not status:
        return jsonify({"success": False, "error": "小说不存在"}), 404
    for key_file in [
        "project.md", "genre_bible.md", "world_bible.md", "characters.md",
        "full_story_arc.md", "volume_plan.md", "alias_registry.md",
    ]:
        content = read_novel_file(novel_name, key_file)
        if content:
            status[key_file.replace(".md", "_content")] = content[:5000]
            fpath = os.path.join(get_novels_dir(), novel_name, key_file)
            if os.path.exists(fpath):
                st = os.stat(fpath)
                status[key_file.replace(".md", "_info")] = {"size": st.st_size, "mtime": st.st_mtime}
    return jsonify({"success": True, "novel": status})


@app.route("/api/novels/<novel_name>/file")
def api_read_file(novel_name):
    file_path = request.args.get("path", "")
    if not file_path or ".." in file_path:
        return jsonify({"success": False, "error": "无效路径"}), 400
    parts = file_path.strip("/").split("/")
    content = read_novel_file(novel_name, *parts)
    if content is None:
        return jsonify({"success": False, "error": "文件不存在"}), 404
    return jsonify({"success": True, "content": content, "path": file_path})


@app.route("/api/novels/<novel_name>/chapters/<path:ch_ref>")
def api_read_chapter(novel_name, ch_ref):
    content = None
    if "/" in ch_ref:
        content = read_novel_file(novel_name, "manuscript", f"{ch_ref}.md")
    else:
        novels_dir = get_novels_dir()
        novel_path = os.path.join(novels_dir, novel_name)
        manuscript_dir = os.path.join(novel_path, "manuscript")
        if os.path.exists(manuscript_dir):
            for vol_dir in sorted(os.listdir(manuscript_dir)):
                ch_file = os.path.join(manuscript_dir, vol_dir, f"{ch_ref}.md")
                if os.path.exists(ch_file):
                    with open(ch_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    ch_ref = f"{vol_dir}/{ch_ref}"
                    break
    if content is None:
        return jsonify({"success": False, "error": "章节不存在"}), 404
    return jsonify({"success": True, "content": content, "path": ch_ref, "word_count": count_words(content)})


@app.route("/api/novels/<novel_name>/chapters/<path:ch_ref>/edit", methods=["POST"])
def api_edit_chapter(novel_name, ch_ref):
    """Save edited chapter content"""
    data = request.json
    content = data.get("content", "")
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    file_path = os.path.join(get_novels_dir(), novel_name, "manuscript", f"{ch_ref}.md")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Sync to content DB
    try:
        from content_db import sync_novel_from_files
        sync_novel_from_files(novel_name)
    except Exception as e:
        logging.warning(f'[sync_novel_from_files] {e}')

    # v3: Auto-update related state
    try:
        from content_db import auto_update_after_save
        parts = ch_ref.split('/')
        volume_str = parts[0] if len(parts) > 1 else 'vol-01'
        ch_match = __import__('re').search(r'ch-(\d+)', ch_ref)
        ch_num = int(ch_match.group(1)) if ch_match else 0
        vol_num = int(volume_str.replace('vol-', '')) if volume_str.startswith('vol-') else 0
        auto_update_after_save(novel_name, vol_num, ch_num, content)
    except Exception as e:
        logging.warning(f'[auto_update_after_save] {e}')

    return jsonify({
        "success": True,
        "message": "章节已保存",
        "path": ch_ref,
        "word_count": count_words(content),
    })


@app.route("/api/novels/<novel_name>/chapters/<path:ch_ref>", methods=["DELETE"])
def api_delete_chapter(novel_name, ch_ref):
    """Delete a chapter with state rollback. Only the latest chapter can be deleted."""
    import re as _re
    from content_db import get_db as _cdb

    # Determine volume and chapter number
    ch_match = _re.search(r'ch-(\d+)', ch_ref)
    if not ch_match:
        return jsonify({"success": False, "error": "无效的章节引用"}), 400
    target_ch_num = int(ch_match.group(1))

    vol_str = "vol-01"
    if "/" in ch_ref:
        vol_str = ch_ref.split("/")[0]
    elif "-ch-" in ch_ref:
        vol_str = ch_ref.split("-ch-")[0]
    vol_num = int(vol_str.replace("vol-", "")) if vol_str.startswith("vol-") else 0

    novels_dir = get_novels_dir()
    novel_path = os.path.join(novels_dir, novel_name)
    manuscript_dir = os.path.join(novel_path, "manuscript")

    if not os.path.isdir(manuscript_dir):
        return jsonify({"success": False, "error": "手稿目录不存在"}), 404

    # ── Check: this must be the latest chapter ──
    all_chapters = []
    for vol_dir in sorted(os.listdir(manuscript_dir)):
        vp = os.path.join(manuscript_dir, vol_dir)
        if not os.path.isdir(vp) or vol_dir.startswith('.'):
            continue
        for f in os.listdir(vp):
            cm = _re.search(r'ch-(\d+)', f)
            if cm and f.endswith('.md'):
                all_chapters.append((vol_dir, int(cm.group(1)), f))

    if not all_chapters:
        return jsonify({"success": False, "error": "没有可删除的章节"}), 404

    all_chapters.sort(key=lambda x: (x[0], x[1]))
    latest_vol, latest_ch, latest_file = all_chapters[-1]
    latest_ref = f"{latest_vol}/ch-{latest_ch:04d}" if len(str(latest_ch)) <= 4 else f"{latest_vol}/ch-{latest_ch:03d}"

    # Normalize ch_ref for comparison — compare by volume + chapter number
    def _parse_ref(ref):
        """Parse chapter ref to (vol_str, ch_num)."""
        ref = ref.replace('-ch-', '/ch-')
        parts = ref.split('/')
        vol_p = parts[0] if len(parts) > 1 else 'vol-01'
        ch_p = parts[-1] if '/' in ref else parts[0]
        m = __import__('re').search(r'ch-(\d+)', ch_p)
        return (vol_p, int(m.group(1)) if m else 0)

    req_vol, req_ch = _parse_ref(ch_ref)
    latest_vol_p, latest_ch_p = _parse_ref(latest_ref)

    if (req_vol, req_ch) != (latest_vol_p, latest_ch_p):
        return jsonify({
            "success": False,
            "error": f"只能从最新章节开始删除。当前最新: {latest_ref}（第{latest_ch}章），你尝试删除: {ch_ref}",
            "latest_chapter": latest_ref,
        }), 400

    # ── Delete chapter file ──
    ch_path = os.path.join(manuscript_dir, f"{ch_ref}.md")
    if not os.path.exists(ch_path):
        # Try alternate path
        alt_path = os.path.join(manuscript_dir, latest_vol, latest_file)
        if os.path.exists(alt_path):
            ch_path = alt_path
        else:
            return jsonify({"success": False, "error": "章节文件不存在"}), 404

    # Read content before deleting (for rollback info)
    chapter_content = ""
    try:
        with open(ch_path, "r", encoding="utf-8") as f:
            chapter_content = f.read()
    except Exception as e:
        logging.warning(f"[chapter-delete] failed to read {ch_path} for rollback: {e}")

    os.remove(ch_path)

    # ── Rollback state ──
    rollback_log = []

    try:
        repo = None
        try:
            from repository import get_repo
            repo = get_repo()
        except Exception as e:
            logging.warning(f"[chapter-delete] failed to obtain repo for rollback: {e}")

        if repo:
            # 1. Delete chapter from DB
            try:
                repo.upsert_chapter(novel_name, ch_ref, volume=vol_str,
                    chapter_num=target_ch_num, content="__DELETED__",
                    title="", word_count=0, content_hash="")
                # Actually remove the record
                import sqlite3 as _sq
                conn = _sq.connect(os.path.join(_PORTAL_DIR, "content.db"))
                conn.execute("DELETE FROM chapters WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"%{ch_ref}%"))
                # Also clean up partial refs
                conn.execute("DELETE FROM chapters WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"{vol_str}/ch-{target_ch_num:03d}%"))
                conn.execute("DELETE FROM chapters WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"{vol_str}/ch-{target_ch_num:04d}%"))
                conn.commit()
                conn.close()
                rollback_log.append("已从数据库删除章节记录")
            except Exception as e:
                rollback_log.append(f"数据库删除异常: {e}")

            # 2. Delete associated reviews
            try:
                conn = _sq.connect(os.path.join(_PORTAL_DIR, "content.db"))
                conn.execute("DELETE FROM reviews WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"%{ch_ref}%"))
                conn.execute("DELETE FROM reviews WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"%ch-{target_ch_num:04d}%"))
                conn.execute("DELETE FROM reviews WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND chapter_ref LIKE ?",
                           (novel_name, f"%ch-{target_ch_num:03d}%"))
                # Also delete review files
                reviews_dir = os.path.join(novel_path, "reviews")
                if os.path.isdir(reviews_dir):
                    import glob as _g
                    for rp in _g.glob(os.path.join(reviews_dir, f"*{target_ch_num:04d}*")):
                        os.remove(rp)
                        rollback_log.append(f"已删除审稿文件: {os.path.basename(rp)}")
                    for rp in _g.glob(os.path.join(reviews_dir, f"*{target_ch_num:03d}*")):
                        os.remove(rp)
                        rollback_log.append(f"已删除审稿文件: {os.path.basename(rp)}")
                conn.commit()
                conn.close()
            except Exception as e:
                rollback_log.append(f"审稿删除异常: {e}")

            # 3. Roll back foreshadowing resolved at this chapter
            try:
                fs_list = repo.list_foreshadowing(novel_name, status="resolved")
                count = 0
                for f_item in fs_list:
                    rv = f_item.get("resolved_vol", 0)
                    rc = f_item.get("resolved_ch", 0)
                    if rv == vol_num and rc == target_ch_num:
                        repo.update_foreshadowing(f_item["id"],
                            status="pending", resolved_vol=0, resolved_ch=0,
                            resolution_note="")
                        count += 1
                if count:
                    rollback_log.append(f"已回滚 {count} 条伏笔状态")
            except Exception as e:
                rollback_log.append(f"伏笔回滚异常: {e}")

            # 4. Update stage gate — decrement current chapter
            gate_file = os.path.join(novel_path, "state", "stage_gate.json")
            if os.path.exists(gate_file):
                try:
                    import json as _j
                    gate = _j.loads(open(gate_file).read())
                    old_ch = gate.get("current_chapter", 0)
                    if old_ch >= target_ch_num:
                        gate["current_chapter"] = max(0, target_ch_num - 1)
                        # Find previous chapter to set as current
                        prev_found = False
                        for vd, cn, fn in reversed(all_chapters[:-1]):
                            gate["current_chapter"] = cn
                            gate["current_volume"] = int(vd.replace("vol-", ""))
                            prev_found = True
                            break
                        if not prev_found:
                            gate["current_chapter"] = 0
                            gate["current_volume"] = 0
                        gate["updated_at"] = __import__('datetime').datetime.now().isoformat()
                        os.makedirs(os.path.dirname(gate_file), exist_ok=True)
                        with open(gate_file, "w") as gf:
                            _j.dump(gate, gf, ensure_ascii=False, indent=2)
                        rollback_log.append(f"已更新阶段进度: 当前章节 {old_ch} → {gate['current_chapter']}")
                except Exception as e:
                    rollback_log.append(f"阶段回滚异常: {e}")

            # 5. Update character current_ch
            try:
                chars = repo.list_characters(novel_name)
                updated = 0
                for c in chars:
                    if c.get("current_vol") == vol_num and c.get("current_ch") == target_ch_num:
                        # Find previous position
                        repo.update_character(c["id"], current_vol=0, current_ch=0)
                        updated += 1
                if updated:
                    rollback_log.append(f"已重置 {updated} 个角色位置")
            except Exception as e:
                rollback_log.append(f"角色状态回滚异常: {e}")

            # 6. Re-sync from filesystem to update DB stats
            try:
                from content_db import sync_novel_from_files
                sync_novel_from_files(novel_name)
            except Exception as e:
                logging.warning(f"[chapter-delete] post-delete re-sync failed for {novel_name}: {e}")

    except Exception as e:
        rollback_log.append(f"回滚异常: {e}")

    # ── Clean up empty manuscript volume dir ──
    for vol_dir in sorted(os.listdir(manuscript_dir)):
        vp = os.path.join(manuscript_dir, vol_dir)
        if os.path.isdir(vp) and not vol_dir.startswith('.'):
            remaining = [f for f in os.listdir(vp) if not f.startswith('.')]
            if not remaining:
                os.rmdir(vp)
                rollback_log.append(f"已清理空卷目录: {vol_dir}")

    return jsonify({
        "success": True,
        "message": f"已删除第{target_ch_num}章并回滚相关状态",
        "deleted_chapter": ch_ref,
        "rollback_log": rollback_log,
    })


@app.route("/api/novels/<novel_name>/reviews/<ch_ref>")
def api_read_review(novel_name, ch_ref):
    content = read_novel_file(novel_name, "reviews", f"{ch_ref}-review.md")
    if content is None:
        content = read_novel_file(novel_name, "reviews", f"{ch_ref}.md")
    if content is None:
        return jsonify({"success": False, "error": "审稿不存在"}), 404
    return jsonify({"success": True, "content": content})


@app.route("/api/novels/<novel_name>/status")
def api_novel_status(novel_name):
    content = read_novel_file(novel_name, "state", "current_status.md")
    if content is None:
        return jsonify({"success": False, "error": "状态文件不存在"}), 404
    return jsonify({"success": True, "content": content})


@app.route("/api/novels/<novel_name>/gate-status")
def api_gate_status(novel_name):
    """Return stage gate progress with auto-detection.

    Checks file existence to determine which phases are complete.
    Writing page uses this to show prerequisites and block generation.
    """
    novel_path = os.path.join(get_novels_dir(), novel_name)
    if not os.path.isdir(novel_path):
        return jsonify({"initialized": False, "error": "小说目录不存在"}), 404

    PHASES = [
        ("phase1_opening", "开书设定", ["project.md"]),
        ("phase2_arc", "长线剧情", ["full_story_arc.md"]),
        ("phase3_volume_outline", "卷级章纲", ["outline"]),
        ("phase4_chapter_planning", "章节规划", ["volume_plan.md", "volume_plan"]),
        ("phase5_writing", "正文写作", ["manuscript"]),
        ("phase6_review", "编辑审稿", ["reviews"]),
        ("phase7_status_update", "状态更新", ["state/current_status.md"]),
    ]

    WRITING_PREREQS = ["phase1_opening", "phase3_volume_outline"]

    phases = {}
    for phase_key, label, indicators in PHASES:
        completed = False
        detail = ""
        for ind in indicators:
            ind_path = os.path.join(novel_path, ind)
            if os.path.exists(ind_path):
                # For directories, check they're non-empty
                if os.path.isdir(ind_path):
                    contents = os.listdir(ind_path)
                    contents = [c for c in contents if not c.startswith('.')]
                    if contents:
                        completed = True
                        detail = f"{ind}/ ({len(contents)} 个文件)"
                        break
                else:
                    completed = True
                    detail = ind
                    break
        if not completed:
            detail = f"缺少: {indicators[0]}"

        phases[phase_key] = {
            "status": "completed" if completed else "pending",
            "label": label,
            "detail": detail,
            "is_writing_prereq": phase_key in WRITING_PREREQS,
        }

    # Try to load stage_gate.json for additional metadata
    gate_file = os.path.join(novel_path, "state", "stage_gate.json")
    current_volume = 0
    current_chapter = 0
    if os.path.exists(gate_file):
        try:
            import json
            gate_data = json.loads(open(gate_file).read())
            current_volume = gate_data.get("current_volume", 0)
            current_chapter = gate_data.get("current_chapter", 0)
            # Merge gate file status overrides
            for pkey, pval in gate_data.get("stages", {}).items():
                if pkey in phases and pval == "completed":
                    phases[pkey]["status"] = pval
        except Exception as e:
            logging.warning(f"[stage-status] failed to parse {gate_file}: {e}")

    writing_ready = all(
        phases[p]["status"] == "completed" for p in WRITING_PREREQS
    )

    return jsonify({
        "initialized": True,
        "novel": novel_name,
        "phases": phases,
        "phase_order": [p[0] for p in PHASES],
        "writing_ready": writing_ready,
        "writing_prereqs": WRITING_PREREQS,
        "current_volume": current_volume,
        "current_chapter": current_chapter,
    })


@app.route("/api/novels/<novel_name>/outline/<vol_ref>")
def api_read_outline(novel_name, vol_ref):
    content = read_novel_file(novel_name, "outline", f"{vol_ref}-chapters.md")
    if content is None:
        content = read_novel_file(novel_name, "outline", vol_ref)
    if content is None:
        return jsonify({"success": False, "error": "大纲不存在"}), 404
    return jsonify({"success": True, "content": content})


@app.route("/api/novels/<novel_name>/outline/<vol_ref>/edit", methods=["POST"])
def api_edit_outline(novel_name, vol_ref):
    """Save edited outline"""
    data = request.json
    content = data.get("content", "")
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    # Save as YAML (not MD)
    write_novel_file(novel_name, content, "outline", f"{vol_ref}-chapters.yaml")

    # Sync chapter outlines to DB (only from .yaml file)
    outline_yaml_path = os.path.join(get_novels_dir(), novel_name, "outline", f"{vol_ref}-chapters.yaml")
    if os.path.exists(outline_yaml_path):
        try:
            from content_db import upsert_chapter_outline
            import yaml
            with open(outline_yaml_path, encoding='utf-8') as f:
                parsed = yaml.safe_load(f)
            if parsed and 'chapters' in parsed:
                for ch in parsed['chapters']:
                    upsert_chapter_outline(novel_name, vol_ref, int(ch['number']), {
                        'title': ch.get('title', ''),
                        'function': ch.get('function', []),
                        'core_events': ch.get('core_events', ''),
                        'foreshadowing': ch.get('foreshadowing', []),
                        'ending_hook': ch.get('ending_hook', ''),
                        'is_danger_scene': ch.get('is_danger_scene', False),
                        'word_count': ch.get('word_count', 0),
                    })
        except Exception as e:
            logging.warning(f"[outline_sync] {e}")

    return jsonify({"success": True, "message": "大纲已保存", "vol": vol_ref})


@app.route("/api/novels/<novel_name>/chapter-outlines/<vol_ref>")
def api_get_chapter_outlines(novel_name, vol_ref):
    """Return all chapter outlines for a volume."""
    try:
        from content_db import get_chapter_outlines
        rows = get_chapter_outlines(novel_name, vol_ref)
        return jsonify({"success": True, "volume": vol_ref, "chapters": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num>", methods=["PUT"])
def api_put_chapter_outline(novel_name, vol_ref, ch_num):
    """Update a single chapter outline."""
    data = request.json
    try:
        from content_db import upsert_chapter_outline
        upsert_chapter_outline(novel_name, vol_ref, ch_num, {
            'title': data.get('title', ''),
            'function': data.get('function', []),
            'core_events': data.get('core_events', ''),
            'foreshadowing': data.get('foreshadowing', []),
            'ending_hook': data.get('ending_hook', ''),
            'is_danger_scene': data.get('is_danger_scene', False),
            'word_count': data.get('word_count', 0),
        })
        return jsonify({"success": True, "message": f"第{ch_num}章大纲已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num>")
def api_read_danger_issue(novel_name, vol_ref, ch_num):
    filename = f"danger_issue_{ch_num.replace('ch-', '')}.md"
    content = read_novel_file(
        novel_name, "outline", f"danger_issue_{vol_ref}", filename
    )
    if content is None:
        return jsonify({"success": False, "error": "危机文件不存在"}), 404
    return jsonify({"success": True, "content": content})


# ─── Export ──────────────────────────────────────────────────────────────────


def _collect_chapters(novel_name):
    """Collect all chapters of a novel ordered by volume/chapter.

    Returns list of dicts: {vol_name, ch_name, ch_ref, title, content, word_count}
    """
    novels_dir = get_novels_dir()
    novel_path = os.path.join(novels_dir, novel_name)
    manuscript_dir = os.path.join(novel_path, "manuscript")
    chapters = []
    if not os.path.exists(manuscript_dir):
        return chapters
    for vol_dir in sorted(os.listdir(manuscript_dir)):
        vol_path = os.path.join(manuscript_dir, vol_dir)
        if not os.path.isdir(vol_path) or vol_dir.startswith('.'):
            continue
        for ch_file in sorted(os.listdir(vol_path)):
            if not ch_file.endswith(".md"):
                continue
            ch_path = os.path.join(vol_path, ch_file)
            with open(ch_path, "r", encoding="utf-8") as f:
                content = f.read()
            ch_name = ch_file.replace(".md", "")
            ch_ref = f"{vol_dir}/{ch_name}"
            # Extract title from first heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ch_name
            wc = count_words(content)
            chapters.append({
                "vol_name": vol_dir,
                "ch_name": ch_name,
                "ch_ref": ch_ref,
                "title": title,
                "content": content,
                "word_count": wc,
            })
    return chapters


def _md_to_plain_text(md_text):
    """Strip markdown formatting for plain text output."""
    text = md_text
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove links keeping text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    return text.strip()


def _md_to_html(md_text, chapter_id=""):
    """Convert markdown text to HTML fragment suitable for EPUB/XHTML."""
    html = md_text
    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    # Bold/italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    # Horizontal rule
    html = re.sub(r'^---+\s*$', '<hr/>', html, flags=re.MULTILINE)
    # Blockquote
    html = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    # Lines that are not HTML tags become paragraphs
    lines = html.split('\n')
    result = []
    in_para = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_para:
                result.append('</p>')
                in_para = False
            continue
        if stripped.startswith('<'):
            if in_para:
                result.append('</p>')
                in_para = False
            result.append(stripped)
        else:
            if not in_para:
                result.append('<p>')
                in_para = True
            else:
                result.append('<br/>')
            result.append(stripped)
    if in_para:
        result.append('</p>')
    return '\n'.join(result)


def _novel_title(novel_name):
    """Get the display title for a novel."""
    project = read_novel_file(novel_name, "project.md")
    if project:
        for line in project.split("\n"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().strip(" #")
                if key in ("书名", "作品名", "title", "Title"):
                    return parts[1].strip()
    return novel_name


def _build_epub(novel_name, chapters):
    """Build a simple EPUB file (ZIP of XHTML) using only Python stdlib."""
    import io
    import zipfile
    from xml.etree.ElementTree import Element, SubElement, tostring

    title = _novel_title(novel_name)
    uid = f"novelforge-{novel_name}"
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed
        zf.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)

        # META-INF/container.xml
        zf.writestr("META-INF/container.xml", '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''')

        # OEBPS/style.css
        css = """body { font-family: serif; line-height: 1.8; margin: 1em 2em; }
h2 { text-align: center; margin-top: 2em; }
h3 { margin-top: 1.5em; }
p { text-indent: 2em; margin: 0.5em 0; }
hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }"""
        zf.writestr("OEBPS/style.css", css)

        # XHTML chapters
        manifest_items = []
        spine_items = []
        ch_xhtml_files = []

        for idx, ch in enumerate(chapters):
            ch_id = f"chapter-{idx + 1}"
            html_body = _md_to_html(ch["content"], ch_id)
            xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
  <title>{_escape_xml(ch["title"])}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h2>{_escape_xml(ch["title"])}</h2>
  <p class="volume-info">[{_escape_xml(ch["vol_name"])} · {_escape_xml(ch["ch_name"])}]</p>
{html_body}
</body>
</html>'''
            filename = f"chapter-{idx + 1}.xhtml"
            ch_xhtml_files.append((filename, ch_id, ch["title"]))
            zf.writestr(f"OEBPS/{filename}", xhtml)
            manifest_items.append(
                f'    <item id="{ch_id}" href="{filename}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'    <itemref idref="{ch_id}"/>')

        # toc.ncx
        nav_points = []
        for idx, (fname, ch_id, ch_title) in enumerate(ch_xhtml_files):
            nav_points.append(
                f'    <navPoint id="navpoint-{idx + 1}" playOrder="{idx + 1}">\n'
                f'      <navLabel><text>{_escape_xml(ch_title)}</text></navLabel>\n'
                f'      <content src="{fname}"/>\n'
                f'    </navPoint>'
            )

        toc_ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{uid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{_escape_xml(title)}</text></docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>'''
        zf.writestr("OEBPS/toc.ncx", toc_ncx)

        # content.opf
        manifest = '\n'.join(
            ['    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
             '    <item id="style" href="style.css" media-type="text/css"/>']
            + manifest_items
        )

        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="book-id">{uid}</dc:identifier>
    <dc:title>{_escape_xml(title)}</dc:title>
    <dc:language>zh-CN</dc:language>
    <dc:date>{now}</dc:date>
    <dc:creator>NovelForge</dc:creator>
    <meta name="cover" content="cover"/>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_items)}
  </spine>
</package>'''
        zf.writestr("OEBPS/content.opf", content_opf)

    return buf.getvalue()


def _escape_xml(text):
    """Escape text for XML/HTML."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def _build_txt(novel_name, chapters):
    """Concatenate all chapters into a plain text file."""
    title = _novel_title(novel_name)
    lines = [f"{title}", "=" * len(title), ""]

    current_vol = None
    for ch in chapters:
        if ch["vol_name"] != current_vol:
            current_vol = ch["vol_name"]
            lines.append("")
            lines.append(f"【{current_vol}】")
            lines.append("-" * 40)
            lines.append("")
        lines.append(f"## {ch['ch_name']} — {ch['title']}")
        lines.append("")
        plain = _md_to_plain_text(ch["content"])
        lines.append(plain)
        lines.append("")
        lines.append("")

    return "\n".join(lines)


def _build_html(novel_name, chapters):
    """Create a single-page HTML reading view with TOC."""
    title = _novel_title(novel_name)

    # Build TOC
    toc_items = []
    chapter_bodies = []
    for idx, ch in enumerate(chapters):
        ch_anchor = f"ch-{idx + 1}"
        toc_items.append(
            f'<li><a href="#{ch_anchor}">[{ch["vol_name"]}] {ch["ch_name"]} — {_escape_xml(ch["title"])}</a></li>'
        )
        html_body = _md_to_html(ch["content"], ch_anchor)
        chapter_bodies.append(f'''
    <div class="chapter" id="{ch_anchor}">
      <h2>{_escape_xml(ch["title"])}</h2>
      <div class="chapter-meta">[{_escape_xml(ch["vol_name"])} · {_escape_xml(ch["ch_name"])} · {ch["word_count"]}字]</div>
      {html_body}
      <div class="back-top"><a href="#toc">↑ 回到目录</a></div>
    </div>''')

    html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape_xml(title)}</title>
  <style>
    body {{ font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; line-height: 1.8; max-width: 800px; margin: 0 auto; padding: 2em 1em; color: #333; }}
    h1 {{ text-align: center; font-size: 2em; margin: 1em 0; }}
    #toc {{ background: #f8f8f8; border: 1px solid #ddd; border-radius: 8px; padding: 1em 2em; margin: 2em 0; }}
    #toc h2 {{ text-align: center; margin-top: 0; }}
    #toc ul {{ list-style: none; padding-left: 0; }}
    #toc li {{ padding: 0.25em 0; border-bottom: 1px dotted #eee; }}
    #toc a {{ text-decoration: none; color: #2a6496; }}
    #toc a:hover {{ text-decoration: underline; }}
    .chapter {{ margin: 3em 0; padding-top: 1em; border-top: 2px solid #eee; }}
    .chapter h2 {{ text-align: center; }}
    .chapter-meta {{ text-align: center; color: #999; font-size: 0.85em; margin-bottom: 1.5em; }}
    .chapter h3 {{ margin-top: 1.5em; }}
    .chapter p {{ text-indent: 2em; margin: 0.6em 0; }}
    .chapter hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
    .chapter blockquote {{ border-left: 3px solid #ccc; margin: 0.5em 0; padding: 0.2em 1em; color: #555; }}
    .chapter code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.9em; }}
    .back-top {{ text-align: right; font-size: 0.85em; margin-top: 1em; }}
    .back-top a {{ color: #2a6496; text-decoration: none; }}
    .volume-info {{ text-align: center; color: #888; font-size: 0.9em; }}
    @media print {{
      body {{ font-size: 12pt; }}
      .back-top {{ display: none; }}
    }}
  </style>
</head>
<body>
  <h1>{_escape_xml(title)}</h1>
  <div class="volume-info">共 {len(chapters)} 章 · 总计 {sum(c['word_count'] for c in chapters)} 字</div>

  <div id="toc">
    <h2>📋 目录</h2>
    <ul>
      {"".join(toc_items)}
    </ul>
  </div>

  {"".join(chapter_bodies)}
</body>
</html>'''

    return html_doc


@app.route("/api/novels/<novel_name>/export")
def api_export_novel(novel_name):
    """Export all chapters of a novel in the requested format."""
    export_format = request.args.get("format", "epub").lower()
    if export_format not in ("epub", "txt", "html"):
        return jsonify({"success": False, "error": "Unsupported format. Use epub, txt, or html."}), 400

    status = get_novel_status(novel_name)
    if not status:
        return jsonify({"success": False, "error": "Novel not found"}), 404

    chapters = _collect_chapters(novel_name)
    if not chapters:
        return jsonify({"success": False, "error": "No chapters found"}), 404

    title = _novel_title(novel_name)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)

    if export_format == "epub":
        data = _build_epub(novel_name, chapters)
        return Response(
            data,
            mimetype="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.epub"',
                "Content-Length": str(len(data)),
            },
        )

    elif export_format == "txt":
        data = _build_txt(novel_name, chapters)
        return Response(
            data,
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.txt"',
            },
        )

    elif export_format == "html":
        data = _build_html(novel_name, chapters)
        return Response(
            data,
            mimetype="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.html"',
            },
        )


# ─── AI & Writing Operations ────────────────────────────────────────────────


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    """Direct AI chat"""
    data = request.json
    messages = data.get("messages", [])
    system = data.get("system", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    top_p = data.get("top_p")

    result = deepseek_chat(
        messages=messages, system_prompt=system,
        temperature=temperature, max_tokens=max_tokens, top_p=top_p,
        operation="ai-chat",
    )
    return jsonify(result)


@app.route("/api/ai/stream", methods=["POST"])
def api_ai_stream():
    """SSE streaming AI chat (supports both Anthropic and OpenAI formats)"""
    data = request.json
    messages = data.get("messages", [])
    system = data.get("system", "")
    user = data.get("user", "")
    # Support {system, user} format from useSSEStream
    if not messages and (system or user):
        messages = [{"role": "user", "content": user}] if user else []
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    top_p = data.get("top_p")
    operation = data.get("operation", "stream-generate")
    novel = data.get("novel", "")

    cfg = get_active_deepseek_config()
    api_key = cfg["api_key"]
    api_base = cfg["api_base"]
    model = cfg["model"]

    if not api_key:
        return jsonify({"success": False, "error": "API Key 未配置"}), 400

    is_anthropic = _is_anthropic_api(api_base)
    temperature_val = temperature if temperature is not None else cfg["temperature"]
    max_tokens_val = max_tokens if max_tokens is not None else cfg["max_tokens"]
    top_p_val = top_p if top_p is not None else cfg["top_p"]

    if is_anthropic:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        endpoint = f"{api_base}/v1/messages"
        payload = _build_anthropic_payload(
            messages, system, model,
            temperature_val, max_tokens_val, top_p_val, stream=True,
        )
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{api_base}/chat/completions"
        payload = _build_openai_payload(
            messages, system, model,
            temperature_val, max_tokens_val, top_p_val, stream=True,
        )

    def generate():
        stream_usage = {}
        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        yield f"data: {json.dumps({'error': f'API错误 {resp.status_code}', 'type': 'error'})}\n\n"
                        return
                    full_text = []

                    if is_anthropic:
                        # Anthropic SSE streaming format
                        current_event = None
                        for line in resp.iter_lines():
                            if line.startswith("event: "):
                                current_event = line[7:].strip()
                            elif line.startswith("data: "):
                                data_str = line[6:]
                                try:
                                    chunk = json.loads(data_str)
                                    event_type = chunk.get("type", "")

                                    if event_type == "content_block_delta":
                                        delta = chunk.get("delta", {})
                                        text = delta.get("text", "")
                                        if text:
                                            full_text.append(text)
                                            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

                                    elif event_type == "message_delta":
                                        usage = chunk.get("usage", {})
                                        if usage:
                                            stream_usage = {
                                                "prompt_tokens": usage.get("input_tokens", 0),
                                                "completion_tokens": usage.get("output_tokens", 0),
                                            }

                                    elif event_type == "message_stop":
                                        yield f"data: {json.dumps({'type': 'done', 'content': ''.join(full_text)})}\n\n"
                                        if stream_usage:
                                            try:
                                                log_token_usage(
                                                    model=model,
                                                    operation=operation or "stream-generate",
                                                    prompt_tokens=stream_usage.get("prompt_tokens", 0),
                                                    completion_tokens=stream_usage.get("completion_tokens", 0),
                                                    novel=novel,
                                                )
                                            except Exception as e:
                                                logging.warning(f"[stream-anthropic] usage log failed: {e}")
                                except json.JSONDecodeError:
                                    continue
                    else:
                        # OpenAI SSE streaming format
                        for line in resp.iter_lines():
                            if line.startswith("data: "):
                                chunk_str = line[6:]
                                if chunk_str == "[DONE]":
                                    yield f"data: {json.dumps({'type': 'done', 'content': ''.join(full_text)})}\n\n"
                                    if stream_usage:
                                        try:
                                            log_token_usage(
                                                model=model,
                                                operation=operation or "stream-generate",
                                                prompt_tokens=stream_usage.get("prompt_tokens", 0),
                                                completion_tokens=stream_usage.get("completion_tokens", 0),
                                                novel=novel,
                                            )
                                        except Exception as e:
                                            logging.warning(f"[stream-openai] usage log failed: {e}")
                                    break
                                try:
                                    chunk = json.loads(chunk_str)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        full_text.append(content)
                                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                                    if "usage" in chunk:
                                        stream_usage = chunk["usage"]
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/novels/create", methods=["POST"])
def api_create_novel():
    data = request.json
    novel_name = data.get("name", "").strip()
    if not novel_name:
        return jsonify({"success": False, "error": "请填写书名"}), 400

    novel_path = os.path.join(get_novels_dir(), novel_name)
    if os.path.exists(novel_path):
        return jsonify({"success": False, "error": "该书已存在"}), 400

    genre = data.get("genre", "")
    protagonist = data.get("protagonist", "")
    selling_point = data.get("selling_point", "")
    word_goal = data.get("word_goal", "100万")
    perspective = data.get("perspective", "第三人称")
    references = data.get("references", "")

    requirements = f"""题材: {genre}
主角设定: {protagonist}
卖点: {selling_point}
篇幅目标: {word_goal}字
叙事视角: {perspective}
参考作品: {references or '无'}

请根据以上信息，生成一部长篇网文的基础资料。"""

    system_prompt = """你是一个专业的小说编辑和类型规则专家。请根据作者提供的需求，生成以下五份小说基础资料文件。

生成格式如下，严格按下面模板输出，每个文件用清晰的标题分隔：

## FILE: project.md
# 作品名：[书名]
# 题材：[题材]
## 简介（200字以内）
[简介内容]

## FILE: genre_bible.md
# 类型规则
## 类型承诺
[内容]
## 核心桥段
[内容]
## 节奏规则
[内容]
## 禁用写法
[内容]

## FILE: world_bible.md
# 世界观设定
## 力量体系
[内容]
## 地理环境
[内容]
## 重要组织
[内容]

## FILE: characters.md
# 人物档案
## 主角
- 姓名：[姓名]
- 性格：[性格描述]
- 目标：[目标]
- 成长弧线：[成长弧线]

## 重要配角
[列表]

## FILE: alias_registry.md
# 别名登记表
[将现实中可能出现的名称替换为虚构别名]"""

    result = deepseek_chat(
        messages=[{"role": "user", "content": requirements}],
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=8192,
        operation="generate-chapter",
    )

    if not result["success"]:
        return jsonify(result)

    content = result["content"]

    os.makedirs(novel_path, exist_ok=True)
    os.makedirs(os.path.join(novel_path, "manuscript"), exist_ok=True)
    os.makedirs(os.path.join(novel_path, "outline"), exist_ok=True)
    os.makedirs(os.path.join(novel_path, "reviews"), exist_ok=True)
    os.makedirs(os.path.join(novel_path, "state"), exist_ok=True)
    os.makedirs(os.path.join(novel_path, "volume_plan"), exist_ok=True)
    os.makedirs(os.path.join(novel_path, "manuscript", "vol-01"), exist_ok=True)

    created_files = []
    current_file = None
    current_content = []
    for line in content.split("\n"):
        file_match = re.match(r"##\s*FILE:\s*(.+)", line)
        if file_match:
            if current_file and current_content:
                filepath = os.path.join(novel_path, current_file)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(current_content))
                created_files.append(current_file)
            current_file = file_match.group(1).strip()
            current_content = []
        elif current_file:
            current_content.append(line)

    if current_file and current_content:
        filepath = os.path.join(novel_path, current_file)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(current_content))
        created_files.append(current_file)

    if "volume_plan.md" not in created_files:
        write_novel_file(novel_name, f"# 分卷规划\n\n## 卷索引\n| 卷号 | 状态 | 章节数 |\n|:---|:---|:---|\n| 01 | 规划中 | 0 |\n", "volume_plan.md")

    if not os.path.exists(os.path.join(novel_path, "state", "current_status.md")):
        write_novel_file(
            novel_name,
            f"# 连载状态\n\n书名: {novel_name}\n总章节: 0\n当前卷: vol-01\n最新章节: 无\n---\n## 人物状态\n（待填写）\n## 设定变更\n（待填写）\n## 伏笔状态\n（待填写）\n## 下一章目标\n（待填写）\n",
            "state", "current_status.md",
        )

    if not os.path.exists(os.path.join(novel_path, "volume_plan", "vol-01.md")):
        write_novel_file(
            novel_name,
            f"# 第一卷规划\n\n卷号: 01\n卷名: 待定\n预计章节: 0\n阶段目标: （待补充）\n",
            "volume_plan", "vol-01.md",
        )

    return jsonify({
        "success": True,
        "novel_name": novel_name,
        "created_files": created_files,
        "ai_response": content,
    })


@app.route("/api/novels/<novel_name>/generate-chapter", methods=["POST"])
def api_generate_chapter(novel_name):
    data = request.json
    chapter_num_raw = data.get("chapter_num", "")
    chapter_num = str(chapter_num_raw) if not isinstance(chapter_num_raw, str) else chapter_num_raw
    volume = data.get("volume", "vol-01")
    style = data.get("style", "")
    user_instructions = data.get("instructions", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")

    novel_path = os.path.join(get_novels_dir(), novel_name)
    ch_num_padded = chapter_num.zfill(3) if chapter_num.isdigit() else chapter_num
    ch_file_path = os.path.join(novel_path, "manuscript", volume, f"ch-{ch_num_padded}.md")
    chapter_exists = os.path.exists(ch_file_path)

    # v3: Use context builder (DB-driven, 9-layer with token budget)
    vol_num_raw = volume.replace("vol-", "")
    vol_int = int(vol_num_raw) if vol_num_raw.isdigit() else 1
    chapter_num = str(chapter_num) if not isinstance(chapter_num, str) else chapter_num
    ch_int = int(chapter_num) if chapter_num.isdigit() else 1

    from context_builder import build_context as _build_ctx
    ctx = _build_ctx({
        "name": novel_name,
        "volume": vol_int,
        "chapter_num": ch_int,
        "style": style if style else "",
        "instructions": user_instructions if user_instructions else "",
        "max_tokens": 10000,
    })
    system_prompt = ctx["system_prompt"]
    # Append chapter-exists hint (context_builder doesn't know this)
    if chapter_exists:
        system_prompt += "\n\n⚠️ 注意：该章节已存在，请基于已有内容续写或重写，保持一致性。"

    result = deepseek_chat(
        messages=[{"role": "user", "content": f"请创作 {volume} 第 {chapter_num} 章"}],
        system_prompt=system_prompt,
        temperature=temperature if temperature is not None else 0.8,
        max_tokens=max_tokens if max_tokens is not None else 8192,
        operation="generate-chapter",
        novel=novel_name,
    )

    if not result["success"]:
        return jsonify(result)

    os.makedirs(os.path.join(novel_path, "manuscript", volume), exist_ok=True)
    filepath = os.path.join(novel_path, "manuscript", volume, f"ch-{ch_num_padded}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result["content"])

    try:
        from content_db import sync_novel_from_files
        sync_novel_from_files(novel_name)
    except Exception as e:
        logging.warning(f'[sync_novel_from_files] {e}')

    return jsonify({
        "success": True,
        "chapter_file": f"{volume}/ch-{ch_num_padded}.md",
        "content": result["content"],
        "usage": result.get("usage", {}),
        "word_count": count_words(result["content"]),
    })


# Validates the chapter_ref path component so it can never escape the
# manuscript dir via ``..`` or contain other path-traversal characters.
# Allowed shape: ``vol-NN/ch-NNN`` (lowercase, digits, exactly one
# ``/`` between the volume and chapter segments, and a ``-`` separating
# the ``vol``/``ch`` prefix from the number). The post-rev flow derives
# ``{chapter_ref}-post-rev{N}`` from the same value, so anything that
# would let an attacker escape the manuscript dir at the chapter_ref
# level is rejected here.
_CHAPTER_REF_PATTERN = re.compile(r"^vol-\d{2}/ch-\d{3}$")


def _normalize_chapter_ref(chapter_ref):
    """Validate ``chapter_ref`` and return the canonical string.

    Rejects:
      * anything that doesn't match the canonical
        ``vol-<NN>/ch-<NNN>`` shape (the existing on-disk convention)
      * any path-traversal character (``..``, leading ``/``, embedded
        ``\\``, etc.)
      * non-alnum/hyphen characters (so we don't have to worry about
        shell metacharacters, control chars, or unicode normalization
        tricks in the path).

    Raises ``ValueError("invalid chapter_ref: <reason>")`` on bad input
    so callers can convert that to a 400 response.
    """
    if not isinstance(chapter_ref, str):
        raise ValueError("invalid chapter_ref: must be a string")
    if not chapter_ref:
        raise ValueError("invalid chapter_ref: must be non-empty")
    if chapter_ref != chapter_ref.strip():
        raise ValueError("invalid chapter_ref: must not have leading/trailing whitespace")
    if ".." in chapter_ref:
        raise ValueError("invalid chapter_ref: '..' is not allowed")
    if "\\" in chapter_ref:
        raise ValueError("invalid chapter_ref: backslashes are not allowed")
    if chapter_ref.startswith("/") or chapter_ref.endswith("/"):
        raise ValueError("invalid chapter_ref: must not start or end with '/'")
    if not _CHAPTER_REF_PATTERN.match(chapter_ref):
        raise ValueError(
            f"invalid chapter_ref: must match vol-NN/ch-NNN shape, got {chapter_ref!r}"
        )
    return chapter_ref


def _run_review(novel_name, chapter_ref, ch_content):
    """Run the 3 review scripts + DeepSeek AI review; return a flat
    review-result dict. NO database writes, NO file writes.

    The returned dict is consumed by:
      * ``_persist_review`` (writes the ``reviews`` row + legacy .md file)
      * the public ``api_review_chapter`` response builder
      * the M5.2 T3 ``api_optimize_chapter`` flow (pre/post reviews)

    Returned keys (public):
      success           bool   — True if the LLM call succeeded
      ai_review         str    — LLM content (or "" on failure)
      word_count        int
      wc_ok             bool
      compliance_ok     bool
      forbidden_ok      bool
      bcontrast_count   int    — parsed from ``binary_contrast_count:``
      tell_count        int    — parsed from ``simple_judgment_groups:``
                                 (kept for backward-compat with the
                                 existing public response and T3 spec;
                                 note: this is NOT the same value as the
                                 DB column ``reviews.tell_count``)
      script_results    dict   — ``{analyze, compliance, forbidden}`` each
                                 ``{"stdout": str, "success": bool}``

    Internal keys (used only by ``_persist_review``):
      _analyze, _compliance, _forbidden   raw run_script outputs
      _bc_count, _jg_count, _tp_count     parsed counts for the DB row
                                          (bc=bc, jg=judgment_groups,
                                          tp=reviews.tell_count column)
    """
    full_ch_path = os.path.join(get_novels_dir(), novel_name, "manuscript", f"{chapter_ref}.md")
    script_results = {}

    analyze = run_script("analyze_chapter.py", full_ch_path, cwd=get_agent_root())
    script_results["analyze"] = analyze

    compliance = run_script("check_compliance.py", full_ch_path, cwd=get_agent_root())
    script_results["compliance"] = compliance

    forbidden = run_script("detect_forbidden_patterns.py", full_ch_path, cwd=get_agent_root())
    script_results["forbidden"] = forbidden

    genre = read_novel_file(novel_name, "genre_bible.md") or ""
    chars = read_novel_file(novel_name, "characters.md") or ""

    system_prompt = f"""你是一个专业的网文编辑审稿Agent。请对以下章节进行全面审稿。

审稿维度：
1. 章节功能：是否服务主线/人物/设定/读者回报
2. 人物一致性：人物行为是否符合档案
3. 设定一致性：新增设定是否与世界背景冲突
4. 节奏：高压/低压是否合理
5. 危机执行：dangger_issue中的危机是否得到体现
6. 结尾牵引：是否有足够的悬念吸引继续阅读

## 小说设定
{genre[:2000]}

## 人物档案
{chars[:2000]}

输出格式（YAML风格）：
```
conclusion: 通过/修改/重写
word_count: <字数>
issues:
  - type: 人物/设定/节奏/功能
    severity: 严重/中等/轻微
    description: ...
strengths:
  - ...
suggestions:
  - ...
```"""

    review_prompt = f"请审稿以下章节：\n\n{ch_content[:8000]}"

    result = deepseek_chat(
        messages=[{"role": "user", "content": review_prompt}],
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=4096,
        operation="review-chapter",
        novel=novel_name,
    )

    # Parse analyze stdout for the structured counts. Parsed ONCE here and
    # shared by both the DB row (_persist_review) and the public response,
    # so the duplicated regex work in the pre-refactor code is gone.
    analyze_stdout = analyze.get("stdout", "")
    bc_match = re.search(r'binary_contrast_count:\s*(\d+)', analyze_stdout)
    bc_count = int(bc_match.group(1)) if bc_match else 0
    jg_match = re.search(r'simple_judgment_groups:\s*(\d+)', analyze_stdout)
    jg_count = int(jg_match.group(1)) if jg_match else 0
    tp_match = re.search(r'tell_patterns:\s*(\d+)', analyze_stdout)
    tp_count = int(tp_match.group(1)) if tp_match else 0

    return {
        "success": result["success"],
        "ai_review": result.get("content", ""),
        "word_count": count_words(ch_content),
        "wc_ok": analyze.get("success") and bool(re.search(r"min_2500_ok:\s*true", analyze_stdout)),
        "compliance_ok": compliance.get("success"),
        "forbidden_ok": forbidden.get("success"),
        "bcontrast_count": bc_count,
        "tell_count": jg_count,
        "script_results": {
            "analyze": {"stdout": analyze.get("stdout", ""), "success": analyze.get("success", False)},
            "compliance": {"stdout": compliance.get("stdout", ""), "success": compliance.get("success", False)},
            "forbidden": {"stdout": forbidden.get("stdout", ""), "success": forbidden.get("success", False)},
        },
        # Internal fields for _persist_review. Prefixed with _ to keep
        # them out of any "public" iteration of the dict.
        "_analyze": analyze,
        "_compliance": compliance,
        "_forbidden": forbidden,
        "_bc_count": bc_count,
        "_jg_count": jg_count,
        "_tp_count": tp_count,
    }


def _persist_review(novel_name, chapter_ref, review_result):
    """Persist a ``_run_review`` result to the ``reviews`` table and write
    the legacy ``reviews/{ch_id}-review.md`` file.

    Mirrors the pre-refactor behavior:
      * On LLM failure (review_result["success"] is False), this is a
        no-op — the previous code only persisted when the LLM call
        succeeded.
      * DB row written first, committed, closed; THEN the .md file is
        written. Persistence order is preserved.
      * Bare try/except wrapping the DB block, so any DB error is
        logged and swallowed (the legacy behavior).
    """
    if not review_result.get("success"):
        return

    analyze = review_result["_analyze"]
    compliance = review_result["_compliance"]
    forbidden = review_result["_forbidden"]
    bc_count = review_result["_bc_count"]
    jg_count = review_result["_jg_count"]
    tp_count = review_result["_tp_count"]
    ch_content_word_count = review_result["word_count"]
    ai_review = review_result.get("ai_review", "")

    ch_id = chapter_ref.replace("/", "-").replace("ch-", "")
    # Sync structured review data to content.db
    try:
        from content_db import get_db as _cdb
        conn = _cdb()
        novel_row = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if novel_row:
            nid = novel_row["id"]
            # Schema-portable upsert: the ``reviews`` table's UNIQUE
            # constraint differs between the SQLAlchemy model
            # (``(novel_id, chapter_ref, created_at)``) and the raw
            # ``content_db.py`` schema (``(novel_id, chapter_ref)``).
            # ``ON CONFLICT(novel_id, chapter_ref)`` only matches the
            # raw schema; in the SQLAlchemy schema it raises
            # "ON CONFLICT clause does not match any PRIMARY KEY or
            # UNIQUE constraint" and the INSERT is rolled back. So we
            # detect the row with a SELECT first and then either
            # UPDATE the existing row or INSERT a new one — portable
            # across both schemas (and any future ones).
            existing = conn.execute(
                "SELECT id FROM reviews WHERE novel_id=? AND chapter_ref=?",
                (nid, chapter_ref),
            ).fetchone()
            row_values = (
                ai_review,
                analyze.get("stdout", "") + "\n" + compliance.get("stdout", "") + "\n" + forbidden.get("stdout", ""),
                1 if analyze.get("success") else 0,
                1 if compliance.get("success") else 0,
                1 if forbidden.get("success") else 0,
                bc_count,
                jg_count,
                tp_count,
                ch_content_word_count,
            )
            if existing:
                conn.execute(
                    """UPDATE reviews SET
                        ai_review=?, script_detail=?,
                        wc_ok=?, compliance_ok=?, forbidden_ok=?,
                        bcontrast_count=?, judgment_groups=?, tell_count=?,
                        word_count=?
                        WHERE id=?""",
                    row_values + (existing["id"],),
                )
            else:
                conn.execute(
                    """INSERT INTO reviews (novel_id, chapter_ref, ai_review, script_detail,
                        wc_ok, compliance_ok, forbidden_ok,
                        bcontrast_count, judgment_groups, tell_count, word_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (nid, chapter_ref) + row_values,
                )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f'[review_sync_to_content_db] {e}')
    review_content = f"""# 审稿报告

日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}
章节: {chapter_ref}

## AI审稿结果
{ai_review}

## 脚本检查结果

### 字数/结构分析
```
{analyze.get('stdout', 'N/A')[:2000]}
```

### 合规检查
```
{compliance.get('stdout', 'N/A')[:2000]}
```

### 禁用模式检测
```
{forbidden.get('stdout', 'N/A')[:2000]}
```
"""
    write_novel_file(novel_name, review_content, "reviews", f"{ch_id}-review.md")


def _diff_reviews(pre, post):
    """Build the ``diff`` block that compares pre-review vs post-review.

    Each value is exposed as a [pre, post] pair so the client can
    render pre→post arrows (or pre/post counts) without re-computing
    the comparison. The ``all_pass`` flag is "is the post-review
    clean?" — i.e. ``post.wc_ok and post.compliance_ok and
    post.forbidden_ok``. It is NOT a comparison: a [True, True]
    pair contributes to ``all_pass=True`` (post still clean), and a
    [False, True] pair also contributes ``True`` (the issue was
    fixed by the optimization). Only a post field that is ``False``
    makes ``all_pass`` ``False``.

    See the response shape spec in
    ``docs/superpowers/plans/2026-06-06-m52-server-side-rereview.md``
    for the full contract.
    """
    def _pair(key):
        return [pre.get(key), post.get(key)]
    return {
        "wc_ok": _pair("wc_ok"),
        "compliance_ok": _pair("compliance_ok"),
        "forbidden_ok": _pair("forbidden_ok"),
        "bcontrast_count": _pair("bcontrast_count"),
        "tell_count": _pair("tell_count"),
        "all_pass": bool(
            post.get("wc_ok")
            and post.get("compliance_ok")
            and post.get("forbidden_ok")
        ),
    }


@app.route("/api/novels/<novel_name>/review-chapter", methods=["POST"])
def api_review_chapter(novel_name):
    data = request.json
    chapter_ref = data.get("chapter_ref", "")
    volume = data.get("volume", "vol-01")
    chapter_num = data.get("chapter_num", "")
    chapter_num = str(chapter_num) if not isinstance(chapter_num, str) else chapter_num
    ch_padded = chapter_num.zfill(3) if chapter_num.isdigit() else chapter_num
    if not chapter_ref:
        chapter_ref = f"{volume}/ch-{ch_padded}"
    else:
        # Normalize chapter_ref: vol-01-ch-001 -> vol-01/ch-001
        chapter_ref = chapter_ref.replace("-ch-", "/ch-")

    # M5.2 T4.1: reject path-traversal characters in chapter_ref
    # BEFORE any file IO. The chapter_ref is used to build on-disk
    # paths (``manuscript/{chapter_ref}.md``) and to key DB rows, so
    # accepting unsanitized user input would let an attacker write
    # outside the manuscript dir.
    try:
        chapter_ref = _normalize_chapter_ref(chapter_ref)
    except ValueError as e:
        return jsonify({"success": False, "error": "invalid chapter_ref"}), 400

    ch_content = read_novel_file(novel_name, "manuscript", f"{chapter_ref}.md")
    if not ch_content:
        return jsonify({"success": False, "error": f"章节不存在: {chapter_ref}"}), 404

    logging.info(f"[review] novel={novel_name} chapter_ref={chapter_ref} volume={volume} chapter_num={chapter_num} word_count_from_file={count_words(ch_content)}")

    result = _run_review(novel_name, chapter_ref, ch_content)
    _persist_review(novel_name, chapter_ref, result)

    return jsonify({
        "success": True,
        "ai_review": result["ai_review"],
        "word_count": result["word_count"],
        "wc_ok": result["wc_ok"],
        "compliance_ok": result["compliance_ok"],
        "forbidden_ok": result["forbidden_ok"],
        "bcontrast_count": result["bcontrast_count"],
        "tell_count": result["tell_count"],
        "script_results": result["script_results"],
    })


@app.route("/api/novels/<novel_name>/optimize-chapter", methods=["POST"])
def api_optimize_chapter(novel_name):
    """One-click optimize: fix issues found during review"""
    data = request.json
    chapter_ref = data.get("chapter_ref", "")
    volume = data.get("volume", "vol-01")
    review_text = data.get("review_text", "")
    script_issues = data.get("script_issues", "")

    # M5.2 T4.1: reject path-traversal characters in chapter_ref
    # BEFORE any file IO. The post-rev NIT-2 fix below writes the
    # optimized content to ``manuscript/{post_review_ref}.md`` (where
    # ``post_review_ref = {chapter_ref}-post-rev{N}``) and cleans it
    # up in a ``finally`` block — accepting unsanitized input would
    # let an attacker write+delete files outside the manuscript dir.
    try:
        chapter_ref = _normalize_chapter_ref(chapter_ref)
    except ValueError as e:
        return jsonify({"success": False, "error": "invalid chapter_ref"}), 400

    is_preview = request.args.get("preview", "").lower() in ("1", "true", "yes", "on")

    ch_content = read_novel_file(novel_name, "manuscript", f"{chapter_ref}.md")
    if not ch_content:
        return jsonify({"success": False, "error": f"章节不存在: {chapter_ref}"}), 404

    system_prompt = f"""你是一个专业的小说编辑。请根据审稿意见优化以下章节。只修复问题，不要改变章节的核心内容和情节走向。

审稿意见：
{review_text[:3000]}

脚本检查发现的问题：
{script_issues[:2000]}

请直接输出优化后的完整章节正文，以原始标题开头。保持字数在原有范围。"""

    result = deepseek_chat(
        messages=[{"role": "user", "content": "请优化以下章节：\n\n" + ch_content[:8000]}],
        system_prompt=system_prompt,
        temperature=0.4,
        max_tokens=8192,
        operation="optimize-chapter",
        novel=novel_name,
    )

    if not result["success"]:
        return jsonify(result)

    if not is_preview:
        # ── M5.2 T3.5: server-side pre+post review with two rows ────
        # The post-optimize flow is:
        #   1. Backup the original chapter to ``.bak/<ref>.rev{N}.md``
        #      and capture ``rev`` for use below (it must be the same
        #      number the post-review row is keyed under).
        #   2. Pre-review against the ORIGINAL content. Runs BEFORE
        #      the save so the analyze/compliance/forbidden scripts
        #      (which read a file path built from ``chapter_ref``)
        #      see the un-optimized on-disk file. Persists at the
        #      original ``chapter_ref``.
        #   3. Save the optimized content. On OSError, restore from
        #      the .bak and return 500. The pre-review row from
        #      step 2 stays in the DB (no rollback) — the .bak
        #      still holds the original on disk, so the pre-review
        #      accurately reflects it.
        #   4. Post-review against the OPTIMIZED content
        #      (``result["content"]``) and persist at
        #      ``{chapter_ref}-post-rev{N}``.
        # The LLM in both reviews uses the in-memory content
        # (``ch_content`` for pre, ``result["content"]`` for post),
        # not a re-read of the file.
        import shutil as _shutil
        bak_dir = os.path.join(get_novels_dir(), novel_name, "manuscript", ".bak")
        os.makedirs(bak_dir, exist_ok=True)
        ch_file = os.path.join(get_novels_dir(), novel_name, "manuscript", f"{chapter_ref}.md")
        rev = 1
        if os.path.exists(ch_file):
            while os.path.exists(os.path.join(bak_dir, f"{chapter_ref.replace('/','-')}.rev{rev}.md")):
                rev += 1
            _shutil.copy2(ch_file, os.path.join(bak_dir, f"{chapter_ref.replace('/','-')}.rev{rev}.md"))
            # Keep only last 5 versions
            bak_files = sorted([f for f in os.listdir(bak_dir) if chapter_ref.replace('/','-') in f])
            for old_f in bak_files[:-5]:
                os.remove(os.path.join(bak_dir, old_f))

        # 2. Pre-review against the ORIGINAL content. Runs BEFORE the
        # save so the analyze/compliance/forbidden scripts read the
        # un-optimized on-disk file (which is the original). The LLM
        # uses ``ch_content`` (the in-memory original).
        pre_result = _run_review(novel_name, chapter_ref, ch_content)
        _persist_review(novel_name, chapter_ref, pre_result)

        # 3. Save the optimized content. On OSError, roll back from
        # the .bak and return 500. The pre-review row from step 2 is
        # NOT rolled back — it accurately reflects the original
        # (which is still on disk in the .bak), and per the "no
        # rollback on review failure" policy the DB history is kept.
        try:
            write_novel_file(novel_name, result["content"], "manuscript", f"{chapter_ref}.md")
        except OSError as e:
            logging.error(f"[optimize-chapter] save failed, rolling back: {e}")
            if os.path.exists(ch_file):
                _shutil.copy2(
                    os.path.join(bak_dir, f"{chapter_ref.replace('/','-')}.rev{rev}.md"),
                    ch_file,
                )
            return jsonify({"success": False, "error": f"save failed: {e}"}), 500

        # Sync the chapters table with the on-disk content. A sync
        # failure must not abort the optimize path — the review can
        # still run on the file directly. Best-effort.
        try:
            from content_db import sync_novel_from_files
            sync_novel_from_files(novel_name)
        except Exception as e:
            logging.warning(f"[sync_novel_from_files after optimize] {e}")

        # 4. Post-review against the OPTIMIZED content. Use the same
        # ``rev`` we computed above so the post-rev{N} suffix and
        # the .bak file are in lockstep. Wrap in try/except so an
        # unexpected post-review error returns 200 with success=False
        # (consistent with the "no rollback" decision for the
        # post-review failure path) rather than crashing the request.
        post_review_ref = f"{chapter_ref}-post-rev{rev}"
        # NIT-2 fix: ``_run_review`` builds a file path from
        # ``chapter_ref`` (``manuscript/vol-01/ch-001-post-rev1.md``)
        # and passes it to the 3 review scripts, which read the
        # file from disk. The post-rev{N} ref is "virtual" — we
        # never saved the file under that name — so the scripts
        # previously got a missing file and reported ``success=False``
        # for all 3 checks. Fix: write the optimized content to the
        # post-rev file (temporarily) before running the post-review,
        # then clean up in a ``finally`` so the manuscript dir
        # doesn't accumulate post-rev stale files. The cleanup runs
        # on both the success and the failure paths.
        #
        # M5.2 T4.1 NIT-2 followup: the NIT-2 fix above would
        # overwrite and then delete a real file if one already exists
        # at the post-rev path (e.g. the user manually saved a draft
        # under that name, or a previous run leaked because cleanup
        # crashed). Capture the pre-existence state and original
        # content BEFORE the write, then restore the original in the
        # ``finally`` so the real file is not clobbered.
        post_rev_path = os.path.join(
            get_novels_dir(), novel_name, "manuscript", f"{post_review_ref}.md"
        )
        pre_existed = os.path.exists(post_rev_path)
        pre_existed_content = (
            open(post_rev_path, encoding="utf-8").read() if pre_existed else None
        )
        try:
            write_novel_file(
                novel_name, result["content"],
                "manuscript", f"{post_review_ref}.md",
            )
            try:
                post_result = _run_review(novel_name, post_review_ref, result["content"])
                _persist_review(novel_name, post_review_ref, post_result)
            except Exception as e:
                logging.error(f"[optimize-chapter] post-review failed: {e}")
                return jsonify({
                    "success": False,
                    "error": "post-review failed",
                    "content": result["content"],
                    "chapter_ref": chapter_ref,
                    "post_review_ref": post_review_ref,
                    "backup": f"{chapter_ref.replace('/','-')}.rev{rev}.md",
                    "word_count": count_words(result["content"]),
                    "usage": result.get("usage", {}),
                    "pre_review": pre_result,
                }), 200
        finally:
            # Restore the original file if one existed; otherwise
            # remove the temp file we wrote. Either way, the
            # manuscript dir ends up in the same state it was in
            # before the post-review ran.
            if pre_existed:
                try:
                    Path(post_rev_path).write_text(
                        pre_existed_content, encoding="utf-8"
                    )
                except OSError as e:
                    logging.warning(
                        f"[optimize-chapter] failed to restore post-rev file: {e}"
                    )
            else:
                if os.path.exists(post_rev_path):
                    try:
                        os.remove(post_rev_path)
                    except OSError as e:
                        logging.warning(
                            f"[optimize-chapter] failed to clean up post-rev file: {e}"
                        )

    response = {
        "success": True,
        "content": result["content"],
        "chapter_ref": chapter_ref,
    }
    if not is_preview:
        response.update({
            "post_review_ref": post_review_ref,
            "backup": f"{chapter_ref.replace('/','-')}.rev{rev}.md",
            "word_count": count_words(result["content"]),
            "usage": result.get("usage", {}),
            "pre_review": pre_result,
            "post_review": post_result,
            "diff": _diff_reviews(pre_result, post_result),
        })
    else:
        response["word_count"] = count_words(result["content"])
        response["usage"] = result.get("usage", {})
        response["preview"] = True
    return jsonify(response)


@app.route("/api/novels/<novel_name>/run-script", methods=["POST"])
def api_run_script(novel_name):
    data = request.json
    script = data.get("script", "")
    filepath = data.get("filepath", "")

    full_path = os.path.join(get_novels_dir(), novel_name, filepath)
    if not os.path.exists(full_path):
        return jsonify({"success": False, "error": f"文件不存在: {filepath}"}), 404

    result = run_script(script, full_path, cwd=get_agent_root())
    return jsonify(result)


@app.route("/api/novels/<novel_name>/file/write", methods=["POST"])
def api_write_novel_file(novel_name):
    """Write/update any file in a novel's directory"""
    data = request.json
    file_path = data.get("path", "")
    content = data.get("content", "")

    if not file_path or ".." in file_path:
        return jsonify({"success": False, "error": "无效路径"}), 400
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    parts = file_path.strip("/").split("/")
    write_novel_file(novel_name, content, *parts)
    return jsonify({"success": True, "message": "已保存", "path": file_path})


@app.route("/api/novels/<novel_name>/update-status", methods=["POST"])
def api_update_status(novel_name):
    data = request.json
    content = data.get("content", "")
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    write_novel_file(novel_name, content, "state", "current_status.md")
    return jsonify({"success": True, "message": "状态已更新"})


# ─── Config ─────────────────────────────────────────────────────────────────


@app.route("/api/config")
def api_get_config():
    cfg = get_active_deepseek_config()
    user_cfg = load_user_deepseek_config()
    key = cfg["api_key"]
    masked_key = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
    return jsonify({
        "success": True,
        "deepseek_configured": bool(cfg["api_key"]),
        "deepseek_model": cfg["model"],
        "deepseek_api_base": cfg["api_base"],
        "deepseek_key_masked": masked_key if cfg["api_key"] else "",
        "deepseek_key_set_via_ui": user_cfg.get("api_key", ""),
        "deepseek_temperature": cfg["temperature"],
        "deepseek_max_tokens": cfg["max_tokens"],
        "deepseek_top_p": cfg["top_p"],
        "agent_root": get_agent_root(),
        "novels_root": get_novels_dir(),
    })


@app.route("/api/config/save", methods=["POST"])
def api_save_config():
    data = request.json or {}
    existing = load_user_deepseek_config()
    # Only use provided values; keep existing for empty fields
    api_key = data.get("api_key", existing.get("api_key", "")).strip()
    api_base = data.get("api_base", existing.get("api_base", "")).strip()
    model = data.get("model", existing.get("model", "")).strip()
    temperature = str(data.get("temperature", existing.get("temperature", ""))).strip()
    max_tokens = str(data.get("max_tokens", existing.get("max_tokens", ""))).strip()
    top_p = str(data.get("top_p", existing.get("top_p", ""))).strip()

    save_user_deepseek_config(
        api_key=api_key, api_base=api_base, model=model,
        temperature=temperature, max_tokens=max_tokens, top_p=top_p,
    )

    cfg = get_active_deepseek_config()
    key = cfg["api_key"]
    masked_key = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"

    return jsonify({
        "success": True,
        "message": "配置已保存",
        "deepseek_configured": bool(cfg["api_key"]),
        "deepseek_model": cfg["model"],
        "deepseek_api_base": cfg["api_base"],
        "deepseek_key_masked": masked_key if cfg["api_key"] else "",
        "deepseek_temperature": cfg["temperature"],
        "deepseek_max_tokens": cfg["max_tokens"],
        "deepseek_top_p": cfg["top_p"],
    })


@app.route("/api/config/test", methods=["POST"])
def api_test_config():
    cfg = get_active_deepseek_config()
    if not cfg["api_key"]:
        return jsonify({"success": False, "error": "API Key 未配置"})

    is_anthropic = _is_anthropic_api(cfg["api_base"])

    if is_anthropic:
        headers = {
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        endpoint = f"{cfg['api_base']}/v1/messages"
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": "Reply with exactly 'OK'."}],
            "max_tokens": 10,
        }
    else:
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        endpoint = f"{cfg['api_base']}/chat/completions"
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": "Hello, reply with exactly 'OK' if you can read this."}],
            "max_tokens": 10,
            "stream": False,
        }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                return jsonify({
                    "success": False,
                    "error": f"API错误 {resp.status_code}: {resp.text[:500]}",
                })
            data = resp.json()
            provider_name = "MiniMax" if is_anthropic else "API"
            return jsonify({
                "success": True,
                "message": f"✅ {provider_name} 连接成功！",
                "model": data.get("model", cfg["model"]),
                "usage": data.get("usage", {}),
            })
    except httpx.ConnectError:
        return jsonify({"success": False, "error": f"无法连接到 {cfg['api_base']}，请检查 API Base URL"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── Wizard ──────────────────────────────────────────────────────────────────

# Genre categories with sub-genres
GENRE_OPTIONS = {
    "玄幻": [
        "东方玄幻", "异界大陆", "王朝争霸", "洪荒封神", "高武世界",
        "另类玄幻", "神话传说", "诸天万界", "凡人流", "无敌流",
        "系统流", "气运流", "血脉觉醒", "儒道至圣", "术士世界",
    ],
    "仙侠": [
        "古典仙侠", "现代修真", "洪荒封神", "神话修真", "幻想修仙",
        "凡人修仙", "剑道独尊", "炼丹炼器", "宗门养成", "轮回转世",
        "修真科技", "灵根觉醒", "仙魔大战", "天道争锋", "散修逆袭",
    ],
    "都市": [
        "都市生活", "异术超能", "重生逆袭", "青春校园", "商战职场",
        "娱乐明星", "医生文", "特种兵", "鉴宝捡漏", "都市修真",
        "神豪系统", "奶爸日常", "极限运动", "美食经营", "风水相术",
    ],
    "科幻": [
        "星际文明", "未来世界", "末世危机", "时空穿梭", "超级科技",
        "进化变异", "机甲战争", "AI觉醒", "星际殖民", "基因编辑",
        "赛博朋克", "废土求生", "太空歌剧", "虚拟世界", "外星入侵",
    ],
    "历史": [
        "架空历史", "秦汉三国", "两晋隋唐", "宋元明清", "历史神话",
        "外国历史", "争霸天下", "科举朝堂", "基建种田", "穿越种田",
        "后宫权谋", "谍战密探", "航海大发现", "草原帝国", "文明崛起",
    ],
    "悬疑": [
        "悬疑侦探", "灵异鬼怪", "恐怖惊悚", "推理探案", "盗墓探险",
        "心理罪案", "法医秦明", "古墓谜题", "诡异游戏", "克苏鲁",
        "阴阳先生", "捉鬼天师", "诅咒解密", "无限循环", "都市传说",
    ],
    "游戏": [
        "虚拟网游", "电子竞技", "游戏异界", "游戏系统",
        "全息游戏", "MOBA竞技", "FPS射击", "生存游戏",
        "卡牌对战", "塔防策略", "开放世界", "roguelike",
    ],
    "军事": [
        "战争幻想", "谍战特工", "军旅生活", "抗战烽火",
        "特种作战", "海军争霸", "空军王牌", "未来战争",
        "佣兵生涯", "军事科技", "边境风云", "维和行动",
    ],
    "武侠": [
        "传统武侠", "新派武侠", "国术无双", "武侠幻想",
        "江湖恩怨", "侠客行", "六扇门", "暗器世家",
        "轻功天下", "内功心法", "刀剑江湖", "武林盟主",
    ],
    "奇幻": [
        "西方奇幻", "史诗奇幻", "剑与魔法", "黑暗奇幻", "现代奇幻",
        "龙与地下城", "精灵史诗", "矮人锻造", "魔法学院",
        "恶魔契约", "神祇战争", "位面穿梭", "亡灵国度",
    ],
    "轻小说": [
        "恋爱日常", "搞笑吐槽", "原生幻想", "青春疼痛",
        "校园恋爱", "异世界转生", "慢生活", "病娇纯爱",
        "反差萌", "甜宠日常", "胃疼文学", "治愈系",
    ],
    "二次元": [
        "同人衍生", "综漫无限", "动漫穿越",
        "漫威DC", "火影海贼", "型月世界",
        "虚拟偶像", "宅文化", "cosplay",
    ],
    "体育": [
        "足球风云", "篮球称霸", "综合竞技", "格斗搏击",
        "围棋象棋", "赛车竞速", "电子竞技", "田径之王",
        "游泳跳水", "网球王子", "乒乓争锋", "冰雪运动",
    ],
}

WIZARD_STEPS = [
    {
        "id": "name", "label": "书名", "type": "input",
        "question": "请为你的小说起一个名字",
        "placeholder": "输入书名，2-5个字为佳",
        "allow_custom": True, "required": True,
    },
    {
        "id": "genre", "label": "题材大类", "type": "select",
        "question": "请选择题材大类",
        "options": [
            {"label": g, "desc": ", ".join(subs)} for g, subs in GENRE_OPTIONS.items()
        ],
        "allow_custom": True, "required": True,
    },
    {
        "id": "subgenre", "label": "题材细分", "type": "multi_select",
        "question": "请选择题材细分方向（可多选）",
        "parent_key": "genre",
        "allow_custom": True, "required": False,
    },
    {
        "id": "word_goal", "label": "篇幅目标", "type": "select",
        "question": "请选择篇幅目标",
        "options": [
            {"label": "50万字", "desc": "短篇网文，快速完本"},
            {"label": "100万字", "desc": "中等篇幅，网文主流"},
            {"label": "200万字", "desc": "长篇巨作，稳定连载"},
            {"label": "300万字", "desc": "超长篇，史诗级叙事"},
        ],
        "allow_custom": True, "required": True,
    },
    {
        "id": "protagonist", "label": "主角设定", "type": "ai",
        "question": "AI 为你推荐主角方案",
        "prompt_template": "你是一个资深网文编辑。请根据已有设定，生成5个主角原型方案。\n\n书名：{name}\n题材：{genre}\n细分：{subgenre}\n篇幅：{word_goal}\n\n每个方案包含：姓名、身份/背景、性格、核心金手指/能力。\n返回JSON数组（仅JSON，不要其他内容）：\n[{{\"label\": \"姓名 · 身份概括\", \"desc\": \"性格+金手指的简要描述（50字内）\"}}, ...]",
        "allow_custom": True, "required": True,
    },
    {
        "id": "selling_point", "label": "核心卖点", "type": "ai",
        "question": "AI 为你推荐卖点方向",
        "prompt_template": "你是一个资深网文编辑。请根据已有设定，推荐5个最有吸引力的核心卖点方向。\n\n书名：{name}\n题材：{genre}\n细分：{subgenre}\n主角：{protagonist}\n篇幅：{word_goal}\n\n卖点即读者最爽的地方。返回JSON数组（仅JSON，不要其他内容）：\n[{{\"label\": \"卖点标签（5-10字）\", \"desc\": \"展开解释（30字内）\"}}, ...]",
        "allow_custom": True, "required": True,
    },
    {
        "id": "world_setting", "label": "世界观方向", "type": "ai",
        "question": "AI 为你推荐世界观方向",
        "prompt_template": "你是一个资深网文编辑。请根据已有设定，推荐4个世界观展开方向。\n\n书名：{name}\n题材：{genre}\n细分：{subgenre}\n主角：{protagonist}\n卖点：{selling_point}\n\n返回JSON数组（仅JSON，不要其他内容）：\n[{{\"label\": \"世界观方向（8-15字）\", \"desc\": \"展开描述力量体系/地理/势力（40字内）\"}}, ...]",
        "allow_custom": True, "required": True,
    },
    {
        "id": "style", "label": "写作风格", "type": "style_select",
        "question": "选择写作风格并设置比例（总和100%）",
        "options": [
            {"label": "金庸风", "desc": "传统武侠，典雅大气"},
            {"label": "古龙风", "desc": "简洁凌厉，意境留白"},
            {"label": "番茄风", "desc": "爽文直白，快节奏"},
            {"label": "辰东风", "desc": "宏大叙事，设定丰富"},
            {"label": "宅猪风", "desc": "东方神话，厚重底蕴"},
            {"label": "猫腻风", "desc": "文艺心机，伏笔深远"},
            {"label": "烽火风", "desc": "华丽辞藻，情感浓烈"},
            {"label": "土豆风", "desc": "热血升级，打脸爽快"},
            {"label": "老鹰风", "desc": "搞笑玩梗，轻松愉快"},
            {"label": "乌贼风", "desc": "诡秘设定，逻辑严密"},
            {"label": "三少风", "desc": "升级打怪，稳定更新"},
            {"label": "江南风", "desc": "青春忧伤，文笔细腻"},
        ],
        "allow_custom": False, "required": True,
    },
]

TOTAL_STEPS = len(WIZARD_STEPS)

@app.route("/api/styles")
def api_styles():
    """Return available writing styles from DB presets + distilled JSON fingerprints."""
    styles = []
    try:
        from repository import get_repo
        repo = get_repo()
        db_styles = repo.list_style_presets()
        for s in db_styles:
            styles.append({
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "prompt": s.get("prompt", ""),
                "distilled": False,
            })
    except Exception as e:
        # DB presets unavailable — fall back to distilled fingerprints only.
        logging.warning(f"[api_styles] repo preset load failed: {e}")

    # Add distilled style fingerprints from agent-system/styles/
    import glob as _glob
    styles_dir = os.path.join(NOVEL_AGENT_ROOT, "agent-system", "styles")
    if os.path.isdir(styles_dir):
        import json as _json
        for fpath in sorted(_glob.glob(os.path.join(styles_dir, "*.json"))):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                name = data.get("author") or data.get("name") or os.path.splitext(os.path.basename(fpath))[0]
                desc = data.get("style_notes") or data.get("description") or data.get("source", "")
                styles.append({
                    "name": name,
                    "description": desc[:200] if desc else "",
                    "distilled": True,
                    "dialogue_ratio": data.get("dialogue_ratio", 0),
                    "sentence_length_mean": data.get("sentence_length_mean", 0),
                })
            except Exception as e:
                # Skip this style file but keep loading the rest.
                logging.warning(f"[api_styles] failed to load style {fpath}: {e}")

    return jsonify({"success": True, "styles": styles})


@app.route("/api/wizard/step", methods=["POST"])
def api_wizard_step():
    data = request.json or {}
    step_index = data.get("step_index", 0)
    selections = data.get("selections", {})

    if step_index >= len(WIZARD_STEPS):
        return jsonify({"success": False, "error": "无效步骤"}), 400

    step = WIZARD_STEPS[step_index]
    step_type = step.get("type", "ai")

    # --- Select type: return fixed options ---
    if step_type == "select" or step_type == "style_select":
        return jsonify({
            "success": True,
            "step": {k: v for k, v in step.items() if k != "prompt_template"},
            "step_index": step_index,
            "total_steps": TOTAL_STEPS,
            "options": step.get("options", []),
            "step_type": step_type,
            "multi": step_type == "style_select",
            "allow_custom": step.get("allow_custom", False),
            "is_last": False,
        })

    # --- Sub-select / Multi-select: options depend on parent selection ---
    if step_type == "multi_select" or step_type == "sub_select":
        parent_key = step.get("parent_key", "genre")
        parent_val = selections.get(parent_key, "")
        sub_options = []
        if parent_val in GENRE_OPTIONS:
            sub_options = [{"label": s, "desc": ""} for s in GENRE_OPTIONS[parent_val]]
        sub_options.append({"label": "其他 / 混合", "desc": "上述分类之外的创新方向"})
        return jsonify({
            "success": True,
            "step": {k: v for k, v in step.items() if k != "prompt_template"},
            "step_index": step_index,
            "total_steps": TOTAL_STEPS,
            "options": sub_options,
            "step_type": step_type,
            "multi": step_type == "multi_select",
            "allow_custom": step.get("allow_custom", False),
            "is_last": False,
            "parent_label": parent_val,
        })

    # --- Input type: just return step info, no AI call ---
    if step_type == "input":
        return jsonify({
            "success": True,
            "step": {"id": step["id"], "label": step["label"], "question": step["question"], "type": "input", "placeholder": step.get("placeholder", "")},
            "step_index": step_index,
            "total_steps": TOTAL_STEPS,
            "step_type": "input",
            "is_last": False,
        })

    # --- AI type: call AI model ---
    context_parts = []
    label_map = {
        "name": "书名", "genre": "题材", "subgenre": "细分", "word_goal": "篇幅",
        "protagonist": "主角", "selling_point": "卖点", "world_setting": "世界观", "style": "风格",
    }
    for key, val in selections.items():
        if val:
            context_parts.append(f"{label_map.get(key, key)}: {val}")
    context = "; ".join(context_parts) if context_parts else "无"

    prompt = step["prompt_template"].format(
        name=selections.get("name", "未命名"),
        genre=selections.get("genre", "未选择"),
        subgenre=selections.get("subgenre", "未选择"),
        protagonist=selections.get("protagonist", "未设定"),
        selling_point=selections.get("selling_point", "未设定"),
        word_goal=selections.get("word_goal", "100万"),
        world_setting=selections.get("world_setting", "未设定"),
        context=context,
    )

    result = deepseek_chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一个专业的网文编辑顾问。你只返回严格JSON格式，不添加任何markdown代码块标记或解释文字。",
        temperature=0.9,
        max_tokens=1024,
        operation="ai-chat",
    )

    if not result["success"]:
        return jsonify(result)

    options = []
    try:
        raw = result["content"].strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            options = [{"label": o.get("label", ""), "desc": o.get("desc", "")} for o in parsed[:6]]
    except (json.JSONDecodeError, Exception):
        match = re.search(r'\[.*\]', result["content"], re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    options = [{"label": o.get("label", ""), "desc": o.get("desc", "")} for o in parsed[:6]]
            except Exception as e:
                logging.warning(f'[ai_options_json_parse] {e}')

    if not options:
        options = [{"label": "请重试", "desc": "AI未能生成有效选项，请点击重试"}]

    return jsonify({
        "success": True,
        "step": {"id": step["id"], "label": step["label"], "question": step["question"], "type": "ai"},
        "step_index": step_index,
        "total_steps": TOTAL_STEPS,
        "options": options,
        "step_type": "ai",
        "allow_custom": step.get("allow_custom", False),
        "is_last": step_index == len(WIZARD_STEPS) - 1,
    })


# ─── Config DB ──────────────────────────────────────────────────────────────

def get_config_db():
    """Return a repository-backed config connection wrapper."""
    from repository import get_repo
    return _RepoConfigWrapper(get_repo())


class _RepoConfigWrapper:
    """Repository-backed config connection for backward compat."""
    def __init__(self, repo):
        self._repo = repo
    def execute(self, sql, params=None):
        return _RepoConfigCursor(self._repo, sql, params)
    def close(self):
        pass
    def commit(self):
        pass


class _RepoConfigCursor:
    def __init__(self, repo, sql, params):
        self._repo = repo
        self._sql = sql.lower()
        self._results = []
        self._idx = 0
        self._parse()
    
    def _parse(self):
        sql = self._sql
        if "banned_words" in sql:
            self._results = [dict(r) for r in self._repo.list_banned_words()]
        elif "compliance_rules" in sql:
            self._results = [dict(r) for r in self._repo.list_compliance_rules()]
        elif "style_presets" in sql:
            self._results = [dict(r) for r in self._repo.list_style_presets()]
        elif "alias_registry" in sql:
            self._results = [dict(r) for r in self._repo.list_alias_registry()]
        elif "deepseek_config" in sql:
            cfg = self._repo.load_all_config()
            self._results = [{"config_key": k, "config_value": v} for k, v in cfg.items()]
    
    def fetchall(self):
        return self._results
    def fetchone(self):
        return self._results[0] if self._results else None

@app.route("/api/config-db/<table>")
def api_config_list(table):
    allowed = {"banned_words", "compliance_rules", "alias_registry", "style_presets"}
    if table not in allowed:
        return jsonify({"success": False, "error": "无效表名"}), 400
    cat = request.args.get("category", "")
    try:
        conn = get_config_db()
        if cat and table == "banned_words":
            rows = conn.execute("SELECT * FROM banned_words WHERE category=? ORDER BY id", (cat,)).fetchall()
        elif cat and table == "compliance_rules":
            rows = conn.execute("SELECT * FROM compliance_rules WHERE category=? ORDER BY id", (cat,)).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        conn.close()
        return jsonify({"success": True, "rows": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/config-db/<table>", methods=["POST"])
def api_config_add(table):
    allowed = {"banned_words", "compliance_rules", "alias_registry", "style_presets"}
    if table not in allowed:
        return jsonify({"success": False, "error": "无效表名"}), 400
    data = request.json or {}
    try:
        conn = get_config_db()
        if table == "banned_words":
            conn.execute("INSERT INTO banned_words (word,category,replacement,severity) VALUES (?,?,?,?)",
                (data["word"], data.get("category","通用"), data.get("replacement",""), data.get("severity","error")))
        elif table == "compliance_rules":
            conn.execute("INSERT INTO compliance_rules (rule_key,rule_value,description,category) VALUES (?,?,?,?)",
                (data["rule_key"], data["rule_value"], data.get("description",""), data.get("category","general")))
        elif table == "alias_registry":
            conn.execute("INSERT INTO alias_registry (real_name,alias,category,notes) VALUES (?,?,?,?)",
                (data["real_name"], data["alias"], data.get("category","地名"), data.get("notes","")))
        elif table == "style_presets":
            conn.execute("INSERT INTO style_presets (name,description,prompt,is_active) VALUES (?,?,?,?)",
                (data["name"], data.get("description",""), data["prompt"], data.get("is_active",1)))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "已添加"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/config-db/<table>/<int:row_id>", methods=["PUT", "DELETE"])
def api_config_manage(table, row_id):
    allowed = {"banned_words", "compliance_rules", "alias_registry", "style_presets"}
    if table not in allowed:
        return jsonify({"success": False, "error": "无效表名"}), 400
    try:
        conn = get_config_db()
        if request.method == "DELETE":
            conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            if table == "banned_words":
                conn.execute("UPDATE banned_words SET word=?,category=?,replacement=?,severity=? WHERE id=?",
                    (data["word"], data.get("category",""), data.get("replacement",""), data.get("severity","error"), row_id))
            elif table == "compliance_rules":
                conn.execute("UPDATE compliance_rules SET rule_key=?,rule_value=?,description=?,category=? WHERE id=?",
                    (data["rule_key"], data["rule_value"], data.get("description",""), data.get("category",""), row_id))
            elif table == "alias_registry":
                conn.execute("UPDATE alias_registry SET real_name=?,alias=?,category=?,notes=? WHERE id=?",
                    (data["real_name"], data["alias"], data.get("category",""), data.get("notes",""), row_id))
            elif table == "style_presets":
                conn.execute("UPDATE style_presets SET name=?,description=?,prompt=?,is_active=? WHERE id=?",
                    (data["name"], data.get("description",""), data["prompt"], data.get("is_active",1), row_id))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Quality Report ─────────────────────────────────────────────────────────

@app.route("/api/content/quality-report/<novel_name>")
def api_quality_report(novel_name):
    try:
        from content_db import get_db as _qdb
        conn = _qdb()
        novel = conn.execute("SELECT * FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        nid = novel["id"]

        # Word count trend (last 30 chapters)
        ch_trend = conn.execute("""SELECT chapter_ref, word_count, created_at FROM chapters
            WHERE novel_id=? ORDER BY chapter_num DESC LIMIT 30""", (nid,)).fetchall()

        # Review pass rates
        total_r = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE novel_id=?", (nid,)).fetchone()["c"]
        wc_pass = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE novel_id=? AND wc_ok=1", (nid,)).fetchone()["c"]
        comp_pass = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE novel_id=? AND compliance_ok=1", (nid,)).fetchone()["c"]
        forb_pass = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE novel_id=? AND forbidden_ok=1", (nid,)).fetchone()["c"]

        # Average binary contrast per chapter
        avg_bc = conn.execute("SELECT AVG(bcontrast_count) as v FROM reviews WHERE novel_id=?", (nid,)).fetchone()["v"] or 0
        avg_tell = conn.execute("SELECT AVG(tell_count) as v FROM reviews WHERE novel_id=?", (nid,)).fetchone()["v"] or 0
        total_jg = conn.execute("SELECT SUM(judgment_groups) as v FROM reviews WHERE novel_id=?", (nid,)).fetchone()["v"] or 0

        # Review quality trend (last 10 reviews)
        rev_trend = conn.execute("""SELECT chapter_ref, wc_ok, compliance_ok, forbidden_ok, bcontrast_count, tell_count, created_at
            FROM reviews WHERE novel_id=? ORDER BY created_at DESC LIMIT 10""", (nid,)).fetchall()

        # Cross-chapter consistency: detect same character mentioned across chapters
        char_check = conn.execute("""
            SELECT c1.chapter_ref as ch1, c2.chapter_ref as ch2, c1.title
            FROM chapters c1 JOIN chapters c2 ON c1.novel_id=c2.novel_id AND c1.chapter_num < c2.chapter_num
            WHERE c1.novel_id=? AND c1.content LIKE '%死%' AND c2.content LIKE '%复活%'
            AND c2.chapter_num - c1.chapter_num < 20
            LIMIT 5
        """, (nid,)).fetchall()

        # Rhythm analysis: check word count volatility
        ch_wc = conn.execute("""SELECT chapter_ref, word_count FROM chapters
            WHERE novel_id=? ORDER BY chapter_num""", (nid,)).fetchall()
        wc_list = [r["word_count"] for r in ch_wc]
        rhythm_issues = []
        if len(wc_list) > 5:
            avg_wc = sum(wc_list) / len(wc_list)
            for i in range(len(wc_list)):
                if wc_list[i] < 1500:
                    rhythm_issues.append({"chapter": ch_wc[i]["chapter_ref"], "issue": "字数过低(" + str(wc_list[i]) + ")", "severity": "warning"})
            # Detect consecutive low-word chapters (fatigue)
            consec_low = 0
            for i in range(len(wc_list)):
                if wc_list[i] < 2000:
                    consec_low += 1
                    if consec_low >= 3:
                        rhythm_issues.append({"chapter": ch_wc[i]["chapter_ref"], "issue": "连续" + str(consec_low) + "章低于2000字(节奏疲劳)", "severity": "error"})
                else:
                    consec_low = 0

        conn.close()

        return jsonify({"success": True, "report": {
            "novel": novel_name,
            "total_chapters": novel["total_chapters"],
            "total_words": novel["total_words"],
            "chapter_trend": [{"ref": r["chapter_ref"], "wc": r["word_count"], "date": r["created_at"][:10]} for r in reversed(ch_trend)],
            "review_stats": {
                "total": total_r,
                "wc_pass_rate": round(wc_pass/max(total_r,1)*100),
                "compliance_pass_rate": round(comp_pass/max(total_r,1)*100),
                "forbidden_pass_rate": round(forb_pass/max(total_r,1)*100),
            },
            "writing_quality": {
                "avg_binary_contrast": round(avg_bc, 1),
                "avg_tell_patterns": round(avg_tell, 1),
                "total_judgment_groups": total_jg,
            },
            "consistency_alerts": [{"ch1": r["ch1"], "ch2": r["ch2"], "title": r["title"]} for r in char_check] if char_check else [],
            "rhythm_alerts": rhythm_issues,
            "review_trend": [{"ref": r["chapter_ref"], "wc_ok": r["wc_ok"], "comp_ok": r["compliance_ok"], "forb_ok": r["forbidden_ok"], "bc": r["bcontrast_count"], "date": r["created_at"][:10]} for r in reversed(rev_trend)],
        }})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Workflow Enforcement ────────────────────────────────────────────────────

@app.route("/api/workflow/preflight/<novel_name>", methods=["POST"])
def api_workflow_preflight(novel_name):
    """Run all pre-generation enforcement scripts. Returns pass/fail for each."""
    data = request.json or {}
    volume = data.get("volume", "vol-01")

    novel_path = os.path.join(get_novels_dir(), novel_name)
    results = {}

    # 1. Stage gate check
    gate = run_script("stage_gate.py", "--project", novel_path, "check", "phase5_writing",
                      cwd=NOVEL_AGENT_ROOT)
    results["stage_gate"] = {"name": "阶段门控", "ok": gate.get("success", False),
        "detail": gate.get("stdout", "")[:500]}

    # 2. Outline existence check
    vol_num = volume.replace("vol-", "")
    outline_path = os.path.join(novel_path, "outline", f"vol-{vol_num}-chapters.md")
    outline_ok = os.path.exists(outline_path)
    results["outline_check"] = {"name": "卷纲存在", "ok": outline_ok,
        "detail": f"outline/vol-{vol_num}-chapters.md {'存在' if outline_ok else '缺失'}"}

    # 3. Danger issue check
    chapter_num = data.get("chapter_num", "")
    chapter_num = str(chapter_num) if not isinstance(chapter_num, str) else chapter_num
    ch_padded = chapter_num.zfill(3) if chapter_num.isdigit() else chapter_num
    di_path = os.path.join(novel_path, "outline", f"danger_issue_{volume}", f"danger_issue_{ch_padded}.md")
    di_ok = os.path.exists(di_path)
    results["danger_issue_check"] = {"name": "危机关卡", "ok": di_ok,
        "detail": f"danger_issue_{ch_padded}.md {'存在' if di_ok else '缺失（不影响生成）'}"}

    # 4. Character file check
    chars_ok = os.path.exists(os.path.join(novel_path, "characters.md"))
    results["characters_check"] = {"name": "人物档案", "ok": chars_ok,
        "detail": "characters.md " + ("存在" if chars_ok else "缺失")}

    # 5. RAG index status
    rag_out = run_script("rag_query.py", novel_name, "--info", cwd=NOVEL_AGENT_ROOT)
    results["rag_status"] = {"name": "RAG 记忆库", "ok": rag_out.get("success", False) or "chunks" in rag_out.get("stdout", ""),
        "detail": rag_out.get("stdout", rag_out.get("stderr", ""))[:300]}

    all_ok = all(r.get("ok", True) or r.get("name") == "危机关卡" for r in results.values())
    return jsonify({"success": True, "all_ok": all_ok, "results": results})


@app.route("/api/workflow/postflight/<novel_name>", methods=["POST"])
def api_workflow_postflight(novel_name):
    """Run all post-generation enforcement scripts."""
    data = request.json or {}
    chapter_ref = data.get("chapter_ref", "")

    novel_path = os.path.join(get_novels_dir(), novel_name)
    ch_path = os.path.join(novel_path, "manuscript", f"{chapter_ref}.md")
    results = {}

    # 1. Review validation
    ch_id = chapter_ref.replace("/", "-").replace("ch-", "")
    review_path = os.path.join(novel_path, "reviews", f"{ch_id}-review.md")
    if os.path.exists(review_path):
        val = run_script("validate_review.py", review_path, cwd=NOVEL_AGENT_ROOT)
        results["review_validation"] = {"name": "审稿验证", "ok": val.get("success", False),
            "detail": val.get("stdout", "")[:300]}
    else:
        results["review_validation"] = {"name": "审稿验证", "ok": False, "detail": "审稿文件不存在"}

    # 2. Continuity check
    cont = run_script("verify_continuity.py", ch_path, cwd=NOVEL_AGENT_ROOT)
    results["continuity"] = {"name": "连续性校验", "ok": cont.get("success", False),
        "detail": cont.get("stdout", "")[:300]}

    # 3. Rhythm check
    rhy = run_script("rhythm_check.py", ch_path, cwd=NOVEL_AGENT_ROOT)
    results["rhythm"] = {"name": "节奏检查", "ok": rhy.get("success", False),
        "detail": rhy.get("stdout", "")[:300]}

    # 4. RAG index update
    rag = run_script("rag_index.py", novel_path, cwd=NOVEL_AGENT_ROOT)
    results["rag_update"] = {"name": "RAG 索引更新", "ok": rag.get("success", False),
        "detail": rag.get("stdout", "")[:300]}

    # 5. Stage gate complete
    gate = run_script("stage_gate.py", "--project", novel_path, "complete", "phase5_writing",
                      cwd=NOVEL_AGENT_ROOT)
    results["stage_complete"] = {"name": "阶段完成", "ok": gate.get("success", False),
        "detail": gate.get("stdout", "")[:300]}

    all_ok = all(r.get("ok", False) for r in results.values())
    return jsonify({"success": True, "all_ok": all_ok, "results": results})


# ─── Full Pipeline Enforcement ────────────────────────────────────────────

@app.route("/api/novels/<novel_name>/enforce-pipeline", methods=["POST"])
def api_enforce_pipeline(novel_name):
    """Run the complete enforcement pipeline for a chapter.
    This is the scripted version of workflow-new-chapter.md Steps 0-10.
    Returns structured results for each enforcement gate.
    """
    data = request.json or {}
    volume = data.get("volume", "vol-01")
    chapter_num_raw = data.get("chapter_num", "")
    chapter_num = str(chapter_num_raw) if not isinstance(chapter_num_raw, str) else chapter_num_raw
    chapter_ref = data.get("chapter_ref", "")

    novel_path = os.path.join(get_novels_dir(), novel_name)
    ch_num_padded = chapter_num.zfill(3) if chapter_num.isdigit() else chapter_num

    if not chapter_ref and chapter_num:
        chapter_ref = f"{volume}/ch-{ch_num_padded}"

    pipeline = {}

    # Step 0: Stage gate
    gate = run_script("stage_gate.py", "--project", novel_path, "check", "phase5_writing")
    pipeline["0_stage_gate"] = {
        "name": "阶段门控检查", "ok": gate.get("success", False),
        "output": gate.get("stdout", gate.get("stderr", ""))[:500]
    }

    # Step 0.5: RAG context (just check index exists)
    rag_check = run_script("rag_query.py", novel_name, "--info")
    has_rag = rag_check.get("success", False) and ("chunks" in rag_check.get("stdout", "").lower() or "Chunks" in rag_check.get("stdout", ""))
    pipeline["0.5_rag_context"] = {
        "name": "RAG 记忆库状态", "ok": has_rag,
        "output": rag_check.get("stdout", "")[:300]
    }

    # Step 3: Analyze + forbidden patterns
    ch_path = os.path.join(novel_path, "manuscript", f"{chapter_ref}.md")
    if os.path.exists(ch_path):
        analyze = run_script("analyze_chapter.py", ch_path)
        pipeline["3a_analyze"] = {
            "name": "章节结构分析", "ok": analyze.get("success", False),
            "output": analyze.get("stdout", "")[:500]
        }
        forbidden = run_script("detect_forbidden_patterns.py", ch_path)
        pipeline["3b_forbidden"] = {
            "name": "禁用模式检测", "ok": forbidden.get("success", False),
            "output": forbidden.get("stdout", "")[:500]
        }
        compliance = run_script("check_compliance.py", ch_path)
        pipeline["3c_compliance"] = {
            "name": "合规审查", "ok": compliance.get("success", False),
            "output": compliance.get("stdout", "")[:500]
        }

    # Step 9: Review validation
    ch_id = chapter_ref.replace("/", "-").replace("ch-", "")
    review_path = os.path.join(novel_path, "reviews", f"{ch_id}-review.md")
    if os.path.exists(review_path):
        val = run_script("validate_review.py", review_path)
        pipeline["9a_review_validation"] = {
            "name": "审稿验证", "ok": val.get("success", False),
            "output": val.get("stdout", "")[:300]
        }
    else:
        pipeline["9a_review_validation"] = {
            "name": "审稿验证", "ok": False, "output": "审稿文件不存在"
        }

    # Continuity check
    if os.path.exists(ch_path):
        cont = run_script("verify_continuity.py", ch_path)
        pipeline["9b_continuity"] = {
            "name": "连续性校验", "ok": cont.get("success", False),
            "output": cont.get("stdout", "")[:500]
        }
        rhythm = run_script("rhythm_check.py", ch_path)
        pipeline["9c_rhythm"] = {
            "name": "节奏检查", "ok": rhythm.get("success", False),
            "output": rhythm.get("stdout", "")[:500]
        }

    # RAG index update
    rag_update = run_script("rag_index.py", novel_path)
    pipeline["9d_rag_update"] = {
        "name": "RAG 索引更新", "ok": rag_update.get("success", False),
        "output": rag_update.get("stdout", "")[:300]
    }

    # Step 10: Agent tracker + stage complete
    agent = run_script("agent_tracker.py", "--stage", "创建单章", ch_path if os.path.exists(ch_path) else novel_path)
    pipeline["10a_agent_tracker"] = {
        "name": "Agent 执行追踪", "ok": agent.get("success", False),
        "output": agent.get("stdout", "")[:500]
    }

    stage_complete = run_script("stage_gate.py", "--project", novel_path, "complete", "phase5_writing")
    pipeline["10b_stage_complete"] = {
        "name": "阶段完成标记", "ok": stage_complete.get("success", False),
        "output": stage_complete.get("stdout", "")[:500]
    }

    # Summary
    gates = [v for k, v in pipeline.items() if v is not None]
    passed = sum(1 for g in gates if g.get("ok", False))
    total = len(gates)
    all_ok = passed == total

    return jsonify({
        "success": True,
        "all_ok": all_ok,
        "passed": passed,
        "total": total,
        "chapter_ref": chapter_ref,
        "pipeline": pipeline,
    })


# ─── Context Builder ───────────────────────────────────────────────

@app.route("/api/context/build", methods=["POST"])
def api_context_build():
    data = request.json or {}
    try:
        from context_builder import build_context
        vol_str = data.get("volume", "1")
        if isinstance(vol_str, str) and vol_str.startswith("vol-"):
            vol_int = int(vol_str.split("-")[1])
        else:
            vol_int = int(vol_str)
        params = {
            "name": data.get("novel", data.get("novel_name", "")),
            "volume": vol_int,
            "chapter_num": int(data.get("chapter_num", 1)),
            "style": data.get("style", ""),
            "instructions": data.get("instructions", ""),
            "max_tokens": int(data.get("max_tokens", 10000)),
        }
        result = build_context(params)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/context/stats/<novel_name>/<int:volume>/<int:chapter>")
def api_context_stats(novel_name, volume, chapter):
    try:
        from context_builder import get_context_stats
        stats = get_context_stats(novel_name, volume, chapter)
        return jsonify({"success": True, **stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── RAG Engine ──────────────────────────────────────────────────────

@app.route("/api/rag/query", methods=["POST"])
def api_rag_query():
    data = request.json or {}
    novel = data.get("novel", "")
    categories = data.get("queries", [])
    max_tokens = int(data.get("total_max_tokens", 10000))
    if not novel or not categories:
        return jsonify({"success": False, "error": "novel and queries required"}), 400
    try:
        from rag_engine import query_categories
        result = query_categories(novel, categories, total_max_tokens=max_tokens)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Init Engine ──────────────────────────────────────────────────────

@app.route("/api/init/full/<novel_name>", methods=["POST"])
def api_init_full(novel_name):
    try:
        from content_db import init_all_from_files
        result = init_all_from_files(novel_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/world-building/init", methods=["POST"])
def api_init_world_building(novel_name):
    try:
        from content_db import init_world_building_from_file
        result = init_world_building_from_file(novel_name)
        return jsonify({"success": True, "message": result.get("message", ""), "created": result.get("created", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/plot-arcs/init", methods=["POST"])
def api_init_plot_arcs(novel_name):
    try:
        from content_db import init_plot_arcs_from_file
        result = init_plot_arcs_from_file(novel_name)
        return jsonify({"success": True, "message": result.get("message", ""), "created": result.get("created", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/pacing/init", methods=["POST"])
def api_init_pacing(novel_name):
    try:
        from content_db import init_pacing_from_outline
        result = init_pacing_from_outline(novel_name)
        return jsonify({"success": True, "message": result.get("message", ""), "created": result.get("created", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/novels/<novel_name>/revelation/init", methods=["POST"])
def api_init_revelation(novel_name):
    try:
        from content_db import init_revelation_from_outline
        result = init_revelation_from_outline(novel_name)
        return jsonify({"success": True, "message": result.get("message", ""), "created": result.get("created", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── New Domain Tables API ─────────────────────────────────────────────

@app.route("/api/genre_rules/<novel_name>")
def api_genre_rules_list(novel_name):
    try:
        from content_db import get_db
        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel: conn.close(); return jsonify({"success": False, "error": "小说不存在"}), 404
        rows = conn.execute("SELECT * FROM genre_rules WHERE novel_id=? ORDER BY rule_category, id", (novel["id"],)).fetchall()
        conn.close()
        return jsonify({"success": True, "items": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/story_volumes/<novel_name>")
def api_story_volumes_list(novel_name):
    try:
        from content_db import get_db
        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel: conn.close(); return jsonify({"success": False, "error": "小说不存在"}), 404
        rows = conn.execute("SELECT * FROM story_volumes WHERE novel_id=? ORDER BY vol_num", (novel["id"],)).fetchall()
        conn.close()
        return jsonify({"success": True, "items": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/volume_plans/<novel_name>")
def api_volume_plans_list(novel_name):
    try:
        from content_db import get_db
        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel: conn.close(); return jsonify({"success": False, "error": "小说不存在"}), 404
        rows = conn.execute("SELECT id, novel_id, vol_num, title, word_count, created_at FROM volume_plans WHERE novel_id=? ORDER BY vol_num", (novel["id"],)).fetchall()
        conn.close()
        return jsonify({"success": True, "items": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/alias_names/<novel_name>")
def api_alias_names_list(novel_name):
    try:
        from content_db import get_db
        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel: conn.close(); return jsonify({"success": False, "error": "小说不存在"}), 404
        rows = conn.execute("SELECT * FROM alias_names WHERE novel_id=? ORDER BY category, id", (novel["id"],)).fetchall()
        conn.close()
        return jsonify({"success": True, "items": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/project_meta/<novel_name>")
def api_project_meta_list(novel_name):
    try:
        from content_db import get_db
        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel: conn.close(); return jsonify({"success": False, "error": "小说不存在"}), 404
        rows = conn.execute("SELECT * FROM project_meta WHERE novel_id=? ORDER BY meta_key", (novel["id"],)).fetchall()
        conn.close()
        return jsonify({"success": True, "items": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Character Management ──────────────────────────────────────────

@app.route("/api/characters/<novel_name>")
def api_characters_list(novel_name):
    try:
        from content_db import get_characters
        items = get_characters(novel_name)
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/characters/<novel_name>/<int:cid>")
def api_character_get(novel_name, cid):
    try:
        from content_db import get_character, get_character_events
        char = get_character(novel_name, cid)
        if not char:
            return jsonify({"success": False, "error": "角色不存在"}), 404
        events = get_character_events(novel_name, cid)
        return jsonify({"success": True, "character": char, "events": events})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/characters/<novel_name>", methods=["POST"])
def api_character_add(novel_name):
    data = request.json or {}
    try:
        from content_db import add_character
        cid = add_character(novel_name, data.get("name", ""),
            role=data.get("role", "配角"),
            gender=data.get("gender", ""), age=data.get("age", ""),
            identity=data.get("identity", ""), personality=data.get("personality", ""),
            appearance=data.get("appearance", ""), background=data.get("background", ""),
            current_status=data.get("current_status", ""),
            current_vol=data.get("current_vol", 0), current_ch=data.get("current_ch", 0),
            lifeline=data.get("lifeline", ""), arc=data.get("arc", ""),
            ending=data.get("ending", ""), notes=data.get("notes", ""))
        return jsonify({"success": True, "id": cid, "message": "角色已添加"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/characters/<novel_name>/<int:cid>", methods=["PUT", "DELETE"])
def api_character_manage(novel_name, cid):
    try:
        from content_db import update_character, delete_character
        if request.method == "DELETE":
            delete_character(cid)
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            update_character(cid, **{k: v for k, v in data.items()
                if k in ["name","role","gender","age","identity","personality",
                         "appearance","background","current_status","current_vol",
                         "current_ch","lifeline","arc","ending","notes",
                         "desire","fear","lie","truth",
                         "ability_level","ability_curve","ability_cost",
                         "emotional_state","emotion_curve","relationship_map",
                         "dilemma","mirror"]})
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/characters/<novel_name>/<int:cid>/event", methods=["POST"])
def api_character_event(novel_name, cid):
    data = request.json or {}
    try:
        from content_db import add_character_event
        eid = add_character_event(novel_name, cid,
            description=data.get("description", ""),
            event_type=data.get("event_type", "状态变更"),
            vol=data.get("vol", 0), ch=data.get("ch", 0),
            chapter_ref=data.get("chapter_ref", ""),
            source=data.get("source", "manual"))
        return jsonify({"success": True, "id": eid, "message": "事件已记录"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/characters/<novel_name>/init", methods=["POST"])
def api_characters_init(novel_name):
    try:
        from content_db import init_characters_from_files
        result = init_characters_from_files(novel_name)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Foreshadowing Management ─────────────────────────────────────────

@app.route("/api/foreshadowing/<novel_name>")
def api_foreshadowing_list(novel_name):
    status = request.args.get("status")
    volume = request.args.get("volume", type=int)
    try:
        from content_db import get_foreshadowing
        items = get_foreshadowing(novel_name, status=status, volume=volume)
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/foreshadowing/<novel_name>/unresolved")
def api_foreshadowing_unresolved(novel_name):
    vol = request.args.get("vol", type=int)
    ch = request.args.get("ch", type=int)
    try:
        from content_db import get_unresolved_foreshadowing
        items = get_unresolved_foreshadowing(novel_name, current_vol=vol, current_ch=ch)
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/foreshadowing/<novel_name>", methods=["POST"])
def api_foreshadowing_add(novel_name):
    data = request.json or {}
    try:
        from content_db import add_foreshadowing
        fid = add_foreshadowing(
            novel_name,
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "剧情"),
            introduced_vol=data.get("introduced_vol", 0),
            introduced_ch=data.get("introduced_ch", 0),
            target_vol=data.get("target_vol", 0),
            target_ch=data.get("target_ch", 0),
            priority=data.get("priority", "normal"),
        )
        return jsonify({"success": True, "id": fid, "message": "伏笔已添加"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/foreshadowing/<novel_name>/<int:fid>", methods=["PUT", "DELETE"])
def api_foreshadowing_manage(novel_name, fid):
    try:
        from content_db import update_foreshadowing, delete_foreshadowing
        if request.method == "DELETE":
            delete_foreshadowing(fid)
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            update_foreshadowing(fid, **{k: v for k, v in data.items()
                if k in ["name","description","category","status","introduced_vol",
                         "introduced_ch","target_vol","target_ch","resolved_vol",
                         "resolved_ch","resolution_note","priority"]})
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/foreshadowing/<novel_name>/resolve/<int:fid>", methods=["POST"])
def api_foreshadowing_resolve(novel_name, fid):
    data = request.json or {}
    try:
        from content_db import resolve_foreshadowing
        resolve_foreshadowing(fid, data.get("vol", 0), data.get("ch", 0),
                             data.get("note", ""))
        return jsonify({"success": True, "message": "伏笔已标记为已填"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/foreshadowing/<novel_name>/init", methods=["POST"])
def api_foreshadowing_init(novel_name):
    try:
        from content_db import init_foreshadowing_from_outline
        result = init_foreshadowing_from_outline(novel_name)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── World Building ───────────────────────────────────────────────────

@app.route("/api/world_building/<novel_name>")
def api_world_building_list(novel_name):
    domain = request.args.get("domain")
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        sql = "SELECT * FROM world_building WHERE novel_id=?"
        params = [novel["id"]]
        if domain:
            sql += " AND domain=?"
            params.append(domain)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = [dict(r) for r in rows]
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/world_building/<novel_name>", methods=["POST"])
def api_world_building_add(novel_name):
    data = request.json or {}
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        conn.execute("""INSERT INTO world_building
            (novel_id, domain, name, content, related_vol, related_ch, tags)
            VALUES (?,?,?,?,?,?,?)""",
            (novel["id"],
             data.get("domain", ""),
             data.get("name", ""),
             data.get("content", ""),
             data.get("related_vol", 0),
             data.get("related_ch", 0),
             data.get("tags", "")))
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "id": row_id, "message": "世界观条目已添加"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/world_building/<novel_name>/<int:row_id>", methods=["PUT", "DELETE"])
def api_world_building_manage(novel_name, row_id):
    try:
        conn = get_content_db()
        if request.method == "DELETE":
            conn.execute("DELETE FROM world_building WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            updates = {k: v for k, v in data.items()
                       if k in ["domain", "name", "content", "related_vol",
                                "related_ch", "tags"]}
            if updates:
                updates["updated_at"] = datetime.now().isoformat()
                set_clause = ", ".join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [row_id]
                conn.execute(f"UPDATE world_building SET {set_clause} WHERE id=?", values)
                conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Plot Arcs ────────────────────────────────────────────────────────

@app.route("/api/plot_arcs/<novel_name>")
def api_plot_arcs_list(novel_name):
    status = request.args.get("status")
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        sql = "SELECT * FROM plot_arcs WHERE novel_id=?"
        params = [novel["id"]]
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = [dict(r) for r in rows]
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/plot_arcs/<novel_name>", methods=["POST"])
def api_plot_arcs_add(novel_name):
    data = request.json or {}
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        miles = data.get("milestones", [])
        milestones = json.dumps(miles) if isinstance(miles, list) else miles
        conn.execute("""INSERT INTO plot_arcs
            (novel_id, name, type, volume_start, chapter_start,
             volume_end, chapter_end, summary, milestones, status, priority)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (novel["id"],
             data.get("name", ""),
             data.get("type", "主线"),
             data.get("volume_start", 0),
             data.get("chapter_start", 0),
             data.get("volume_end", 0),
             data.get("chapter_end", 0),
             data.get("summary", ""),
             milestones,
             data.get("status", "active"),
             data.get("priority", "normal")))
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "id": row_id, "message": "剧情弧已添加"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/plot_arcs/<novel_name>/<int:row_id>", methods=["PUT", "DELETE"])
def api_plot_arcs_manage(novel_name, row_id):
    try:
        conn = get_content_db()
        if request.method == "DELETE":
            conn.execute("DELETE FROM plot_arcs WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            updates = {k: v for k, v in data.items()
                       if k in ["name", "type", "volume_start", "chapter_start",
                                "volume_end", "chapter_end", "summary", "milestones",
                                "status", "priority"]}
            if "milestones" in updates and isinstance(updates["milestones"], list):
                updates["milestones"] = json.dumps(updates["milestones"])
            if updates:
                updates["updated_at"] = datetime.now().isoformat()
                set_clause = ", ".join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [row_id]
                conn.execute(f"UPDATE plot_arcs SET {set_clause} WHERE id=?", values)
                conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Pacing Control ───────────────────────────────────────────────────

@app.route("/api/pacing_control/<novel_name>")
def api_pacing_control_list(novel_name):
    volume = request.args.get("volume", type=int)
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        sql = "SELECT * FROM pacing_control WHERE novel_id=?"
        params = [novel["id"]]
        if volume is not None:
            sql += " AND volume=?"
            params.append(volume)
        sql += " ORDER BY volume, chapter_start"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = [dict(r) for r in rows]
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pacing_control/<novel_name>", methods=["POST"])
def api_pacing_control_add(novel_name):
    data = request.json or {}
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        conn.execute("""INSERT INTO pacing_control
            (novel_id, volume, chapter_start, chapter_end, pace_type,
             intensity, emotion_target, word_budget_min, word_budget_max, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (novel["id"],
             data.get("volume", 0),
             data.get("chapter_start", 0),
             data.get("chapter_end", 0),
             data.get("pace_type", "过渡"),
             data.get("intensity", 5),
             data.get("emotion_target", ""),
             data.get("word_budget_min", 2500),
             data.get("word_budget_max", 3500),
             data.get("notes", "")))
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "id": row_id, "message": "节奏控制已添加"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pacing_control/<novel_name>/<int:row_id>", methods=["PUT", "DELETE"])
def api_pacing_control_manage(novel_name, row_id):
    try:
        conn = get_content_db()
        if request.method == "DELETE":
            conn.execute("DELETE FROM pacing_control WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            updates = {k: v for k, v in data.items()
                       if k in ["volume", "chapter_start", "chapter_end",
                                "pace_type", "intensity", "emotion_target",
                                "word_budget_min", "word_budget_max", "notes"]}
            if updates:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [row_id]
                conn.execute(f"UPDATE pacing_control SET {set_clause} WHERE id=?", values)
                conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Revelation Schedule ──────────────────────────────────────────────

@app.route("/api/revelation_schedule/<novel_name>")
def api_revelation_schedule_list(novel_name):
    volume = request.args.get("volume", type=int)
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        sql = "SELECT * FROM revelation_schedule WHERE novel_id=?"
        params = [novel["id"]]
        if volume is not None:
            sql += " AND reveal_volume=?"
            params.append(volume)
        sql += " ORDER BY priority DESC, reveal_volume, reveal_chapter"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = [dict(r) for r in rows]
        return jsonify({"success": True, "items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/revelation_schedule/<novel_name>", methods=["POST"])
def api_revelation_schedule_add(novel_name):
    data = request.json or {}
    try:
        conn = get_content_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            conn.close()
            return jsonify({"success": False, "error": "小说不存在"}), 404
        conn.execute("""INSERT INTO revelation_schedule
            (novel_id, name, info_type, reveal_volume, reveal_chapter,
             content, audience_knows, protagonist_knows, priority)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (novel["id"],
             data.get("name", ""),
             data.get("info_type", "世界观"),
             data.get("reveal_volume", 0),
             data.get("reveal_chapter", 0),
             data.get("content", ""),
             data.get("audience_knows", 0),
             data.get("protagonist_knows", 0),
             data.get("priority", "normal")))
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "id": row_id, "message": "揭示计划已添加"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/revelation_schedule/<novel_name>/<int:row_id>", methods=["PUT", "DELETE"])
def api_revelation_schedule_manage(novel_name, row_id):
    try:
        conn = get_content_db()
        if request.method == "DELETE":
            conn.execute("DELETE FROM revelation_schedule WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已删除"})
        else:
            data = request.json or {}
            updates = {k: v for k, v in data.items()
                       if k in ["name", "info_type", "reveal_volume",
                                "reveal_chapter", "content", "audience_knows",
                                "protagonist_knows", "priority"]}
            if updates:
                updates["updated_at"] = datetime.now().isoformat()
                set_clause = ", ".join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [row_id]
                conn.execute(f"UPDATE revelation_schedule SET {set_clause} WHERE id=?", values)
                conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Cleanup ─────────────────────────────────────────────────────────

@app.route("/api/novels/<novel_name>/cleanup-bak", methods=["POST"])
def api_cleanup_bak(novel_name):
    """Delete all .bak backup files for a novel"""
    import shutil
    bak_dir = os.path.join(get_novels_dir(), novel_name, "manuscript", ".bak")
    if not os.path.exists(bak_dir):
        return jsonify({"success": True, "deleted": 0, "message": "无备份文件"})
    count = 0
    try:
        for f in os.listdir(bak_dir):
            os.remove(os.path.join(bak_dir, f))
            count += 1
        os.rmdir(bak_dir)
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "deleted": count}), 500
    return jsonify({"success": True, "deleted": count, "message": f"已删除 {count} 个备份文件"})


# ─── Content DB ────────────────────────────────────────────────────────────

@app.route("/api/content/search")
def api_content_search():
    q = request.args.get("q", "")
    novel = request.args.get("novel", "")
    limit = int(request.args.get("limit", 20))
    if not q:
        return jsonify({"success": False, "error": "请提供查询词"}), 400
    results = search_all(q, novel_name=novel or None, limit=limit)
    return jsonify({"success": True, "query": q, "results": results})

@app.route("/api/content/stats/<novel_name>")
def api_content_stats(novel_name):
    stats = get_novel_stats(novel_name)
    if stats is None or "error" in stats:
        return jsonify({"success": False, "error": (stats or {}).get("error", "novel not found")}), 404
    return jsonify({"success": True, "stats": stats})

@app.route("/api/content/sync", methods=["POST"])
def api_content_sync():
    data = request.json or {}
    novel = data.get("novel", "")
    if novel:
        result = sync_novel_from_files(novel)
    else:
        result = {"synced": sync_all_novels()}
    return jsonify({"success": True, "result": result})

# Auto-sync after chapter save: hook into chapter edit
_original_edit_chapter = None


# ─── Templates ──────────────────────────────────────────────────────────────


@app.route("/api/templates")
def api_list_templates():
    templates_dir = get_templates_dir()
    templates = {}
    if os.path.exists(templates_dir):
        for f in os.listdir(templates_dir):
            if f.endswith(".md"):
                filepath = os.path.join(templates_dir, f)
                with open(filepath, "r", encoding="utf-8") as fh:
                    templates[f] = fh.read()[:2000]
    return jsonify({"success": True, "templates": templates})


# ─── Usage Stats ────────────────────────────────────────────────────────────

@app.route("/api/usage/stats")
def api_usage_stats():
    """Return token usage statistics."""
    novel_filter = request.args.get("novel", "")
    days = int(request.args.get("days", 30))

    try:
        conn = _sqlite3.connect(USAGE_DB_PATH)
        conn.row_factory = _sqlite3.Row

        # Total tokens and cost
        total = conn.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens, "
            "COALESCE(SUM(cost_estimate), 0) AS total_cost FROM usage"
        ).fetchone()

        # Breakdown by operation
        by_operation = {}
        op_rows = conn.execute(
            "SELECT operation, COUNT(*) AS calls, COALESCE(SUM(total_tokens), 0) AS tokens, "
            "COALESCE(SUM(cost_estimate), 0) AS cost "
            "FROM usage GROUP BY operation ORDER BY tokens DESC"
        ).fetchall()
        for row in op_rows:
            by_operation[row["operation"]] = {
                "calls": row["calls"],
                "tokens": row["tokens"],
                "cost": round(row["cost"], 6),
            }

        # Breakdown by novel
        by_novel = {}
        novel_rows = conn.execute(
            "SELECT novel, COUNT(*) AS calls, COALESCE(SUM(total_tokens), 0) AS tokens, "
            "COALESCE(SUM(cost_estimate), 0) AS cost "
            "FROM usage WHERE novel != '' GROUP BY novel ORDER BY tokens DESC"
        ).fetchall()
        for row in novel_rows:
            by_novel[row["novel"]] = {
                "calls": row["calls"],
                "tokens": row["tokens"],
                "cost": round(row["cost"], 6),
            }

        # Daily usage for last N days
        daily = []
        daily_rows = conn.execute(
            "SELECT date(created_at) AS day, COUNT(*) AS calls, "
            "COALESCE(SUM(total_tokens), 0) AS tokens, "
            "COALESCE(SUM(cost_estimate), 0) AS cost "
            "FROM usage "
            "WHERE created_at >= datetime('now', ?) "
            "GROUP BY day ORDER BY day ASC",
            (f"-{days} days",)
        ).fetchall()
        for row in daily_rows:
            daily.append({
                "day": row["day"],
                "calls": row["calls"],
                "tokens": row["tokens"],
                "cost": round(row["cost"], 6),
            })

        conn.close()

        return jsonify({
            "success": True,
            "total_tokens": total["total_tokens"],
            "total_cost": round(total["total_cost"], 6),
            "by_operation": by_operation,
            "by_novel": by_novel,
            "daily": daily,
            "days": days,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Start ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = get_active_deepseek_config()
    api_key_status = "已配置" if cfg["api_key"] else "未配置（可在设置页面配置）"
    config_source = "用户设置" if cfg["user_configured"] else "环境变量"
    print(f"\n{'='*60}")
    print(f"  小说写作 Agent Web Portal — NovelForge")
    print(f"{'='*60}")
    print(f"  📂 项目目录: {NOVEL_AGENT_ROOT}")
    print(f"  🤖 AI API: {api_key_status} ({config_source})")
    print(f"  📡 API Base: {cfg['api_base']}")
    print(f"  🧠 模型: {cfg['model']}")
    print(f"  🌡️  温度: {cfg['temperature']} / MaxTokens: {cfg['max_tokens']} / TopP: {cfg['top_p']}")
    print(f"  🌐 访问地址: http://localhost:{PORTAL_PORT}")
    print(f"  ⚙️  设置页面可随时修改所有参数")
    print(f"{'='*60}\n")
    app.run(host=PORTAL_HOST, port=PORTAL_PORT, debug=DEBUG)


@app.route("/api/characters/<novel_name>/<int:cid>/ai-profile", methods=["POST"])
def api_ai_character_profile(novel_name, cid):
    try:
        from content_db import get_character
        char = get_character(novel_name, cid)
        if not char:
            return jsonify({"success": False, "error": "role not found"}), 404

        context = f"Name: {char['name']}\nRole: {char.get('role','')}\n"
        if char.get('identity'): context += f"Identity: {char['identity']}\n"
        if char.get('personality'): context += f"Personality: {char['personality']}\n"
        if char.get('background'): context += f"Background: {char['background'][:500]}\n"

        cfg = get_active_deepseek_config()
        resp = httpx.post(
            f"{cfg['api_base']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": "You are a professional web novel character designer. Generate a complete 8-dimension character profile in JSON. Output ONLY JSON, no markdown. Fields: desire, fear, lie, truth, personality, arc, lifeline, ending, ability_level, ability_curve, ability_cost, emotional_state, emotion_curve, relationship_map (JSON array of {target,type,start,conflict,end}), dilemma (JSON array of {vol,dilemma,choice,cost,gained} - 1-2 per volume), mirror (JSON array of {character,mirrors,contrast}), notes."},
                    {"role": "user", "content": f"Generate 8-dimension profile for this character:\n{context}"},
                ],
                "temperature": 0.7, "max_tokens": 4096,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": f"API error {resp.status_code}"}), 500

        result = resp.json()
        text = result["choices"][0]["message"]["content"]
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return jsonify({"success": False, "error": "AI did not return valid JSON", "raw": text[:500]}), 500

        profile = json.loads(json_match.group(0))
        return jsonify({"success": True, "profile": profile, "usage": result.get("usage", {})})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
