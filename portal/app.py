"""Novel Agent Web Portal - 直接连接DeepSeek的写作Web Portal"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from functools import wraps

import httpx
from flask import Flask, jsonify, render_template, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS

import sqlite3 as _sqlite3

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

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# ─── DeepSeek User Config Persistence ──────────────────────────────────────

DEEPSEEK_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek_config.json")


def load_user_deepseek_config():
    try:
        if os.path.exists(DEEPSEEK_CONFIG_PATH):
            with open(DEEPSEEK_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
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
            if os.path.isdir(vol_path):
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


# ─── DeepSeek API ───────────────────────────────────────────────────────────

def deepseek_chat(messages, system_prompt=None, temperature=None, max_tokens=None, top_p=None, stream=False):
    cfg = get_active_deepseek_config()
    api_key = cfg["api_key"]
    api_base = cfg["api_base"]
    model = cfg["model"]

    if not api_key:
        return {"success": False, "error": "DEEPSEEK_API_KEY 未配置，请在设置页面中配置"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    payload = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature if temperature is not None else cfg["temperature"],
        "max_tokens": max_tokens if max_tokens is not None else cfg["max_tokens"],
        "top_p": top_p if top_p is not None else cfg["top_p"],
        "stream": stream,
    }

    if not stream:
        try:
            with httpx.Client(timeout=300) as client:
                resp = client.post(
                    f"{api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API错误 {resp.status_code}: {resp.text}",
                    }
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return {"success": True, "content": content, "usage": data.get("usage", {})}
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        # Return the client + payload for streaming
        return {"__stream__": True, "payload": payload, "headers": headers, "api_base": api_base}


# ─── API Routes ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
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
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": "章节已保存",
        "path": ch_ref,
        "word_count": count_words(content),
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

    write_novel_file(novel_name, content, "outline", f"{vol_ref}-chapters.md")
    return jsonify({"success": True, "message": "大纲已保存", "vol": vol_ref})


@app.route("/api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num>")
def api_read_danger_issue(novel_name, vol_ref, ch_num):
    filename = f"danger_issue_{ch_num.replace('ch-', '')}.md"
    content = read_novel_file(
        novel_name, "outline", f"danger_issue_{vol_ref}", filename
    )
    if content is None:
        return jsonify({"success": False, "error": "危机文件不存在"}), 404
    return jsonify({"success": True, "content": content})


# ─── AI & Writing Operations ────────────────────────────────────────────────


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    """Direct DeepSeek chat"""
    data = request.json
    messages = data.get("messages", [])
    system = data.get("system", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    top_p = data.get("top_p")

    result = deepseek_chat(
        messages=messages, system_prompt=system,
        temperature=temperature, max_tokens=max_tokens, top_p=top_p,
    )
    return jsonify(result)


@app.route("/api/ai/stream", methods=["POST"])
def api_ai_stream():
    """SSE streaming DeepSeek chat"""
    data = request.json
    messages = data.get("messages", [])
    system = data.get("system", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    top_p = data.get("top_p")

    cfg = get_active_deepseek_config()
    api_key = cfg["api_key"]
    api_base = cfg["api_base"]
    model = cfg["model"]

    if not api_key:
        return jsonify({"success": False, "error": "API Key 未配置"}), 400

    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    payload = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature if temperature is not None else cfg["temperature"],
        "max_tokens": max_tokens if max_tokens is not None else cfg["max_tokens"],
        "top_p": top_p if top_p is not None else cfg["top_p"],
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def generate():
        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("POST", f"{api_base}/chat/completions", headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        yield f"data: {json.dumps({'error': f'API错误 {resp.status_code}', 'type': 'error'})}\n\n"
                        return
                    full_text = []
                    for line in resp.iter_lines():
                        if line.startswith("data: "):
                            chunk_str = line[6:]
                            if chunk_str == "[DONE]":
                                yield f"data: {json.dumps({'type': 'done', 'content': ''.join(full_text)})}\n\n"
                                break
                            try:
                                chunk = json.loads(chunk_str)
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content:  # filter null/empty
                                    full_text.append(content)
                                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
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
    chapter_num = data.get("chapter_num", "")
    volume = data.get("volume", "vol-01")
    style = data.get("style", "")
    user_instructions = data.get("instructions", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")

    novel_path = os.path.join(get_novels_dir(), novel_name)
    context = {}

    for key_file in [
        "project.md", "genre_bible.md", "world_bible.md",
        "characters.md", "full_story_arc.md", "alias_registry.md",
    ]:
        content = read_novel_file(novel_name, key_file)
        if content:
            context[key_file] = content

    status = read_novel_file(novel_name, "state", "current_status.md")
    if status:
        context["current_status.md"] = status

    vol_num = volume.replace("vol-", "")
    outline = read_novel_file(novel_name, "outline", f"vol-{vol_num}-chapters.md")
    if outline:
        context["outline"] = outline

    ch_num_padded = chapter_num.zfill(4) if chapter_num.isdigit() else chapter_num
    danger_issue = read_novel_file(
        novel_name, "outline", f"danger_issue_{volume}", f"danger_issue_{ch_num_padded}.md",
    )
    if danger_issue:
        context["danger_issue"] = danger_issue

    ch_file_path = os.path.join(novel_path, "manuscript", volume, f"ch-{ch_num_padded}.md")
    chapter_exists = os.path.exists(ch_file_path)

    prev_content = ""
    if chapter_num.isdigit():
        prev_num = int(chapter_num) - 1
        if prev_num > 0:
            prev_padded = str(prev_num).zfill(4)
            prev_path = os.path.join(novel_path, "manuscript", volume, f"ch-{prev_padded}.md")
            if os.path.exists(prev_path):
                with open(prev_path, "r", encoding="utf-8") as f:
                    prev_content = f.read()

    context_text = ""
    for fname, fcontent in context.items():
        context_text += f"\n=== {fname} ===\n{fcontent[:3000]}\n"

    if prev_content:
        context_text += f"\n=== 上一章结尾 ===\n{prev_content[-2000:]}\n"

    system_prompt = f"""你是一个专业的长篇网文写作Agent。你的任务是**严格按照大纲和卷纲**写出高质量的小说章节。

## ⚠️ 脚本强制约束（不可跳过）
1. **必须严格遵循大纲/卷纲指定的本章内容**，不得偏离或跳过
2. **必须体现危机/关卡要求**（如果有danger_issue），不得遗漏
3. 严格遵守类型规则和世界观设定
4. 人物行为必须符合人物档案
5. 不得使用真实地名、人名（使用虚构别名）
6. 每章正文纯字数不少于2500字
7. **禁止以下文笔问题**：
   - 禁止使用"不是...而是..."二元对照句式（全文不超过1次）
   - 禁止连续使用"不是"/"是的"/"没有"等简单判断句超过2句
   - 禁止"XX说：+ 对话"的生硬对话引入方式，改用动作+对话自然衔接
   - 禁止大段内心独白式的解释说明（show, don't tell）
8. **语言质量要求**：
   - 每段落至少2-3句话，避免连续单句段
   - 描写与环境结合，不要孤立写景/写人
   - 对话占比控制在30-50%，平衡叙述与对白
   - 关键情节用具体场景呈现，不要概括叙述
9. 必须有明确的章节功能和结尾牵引（悬念/钩子）

## 当前项目上下文
{context_text}

## 风格要求
{style if style else '默认（项目基线风格）'}

## 用户额外指示
{user_instructions if user_instructions else '无'}

{'## 注意：该章节已存在，请基于已有内容续写或重写，保持一致性' if chapter_exists else '## 注意：这是新章节，从头开始创作'}

请直接输出完整的章节正文，以'# 章节标题'开头。"""

    result = deepseek_chat(
        messages=[{"role": "user", "content": f"请创作 {volume} 第 {chapter_num} 章"}],
        system_prompt=system_prompt,
        temperature=temperature if temperature is not None else 0.8,
        max_tokens=max_tokens if max_tokens is not None else 8192,
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
    except Exception:
        pass

    return jsonify({
        "success": True,
        "chapter_file": f"{volume}/ch-{ch_num_padded}.md",
        "content": result["content"],
        "usage": result.get("usage", {}),
        "word_count": count_words(result["content"]),
    })


@app.route("/api/novels/<novel_name>/review-chapter", methods=["POST"])
def api_review_chapter(novel_name):
    data = request.json
    chapter_ref = data.get("chapter_ref", "")
    volume = data.get("volume", "vol-01")
    chapter_num = data.get("chapter_num", "")

    ch_padded = chapter_num.zfill(4) if chapter_num.isdigit() else chapter_num
    if not chapter_ref:
        chapter_ref = f"{volume}/ch-{ch_padded}"

    ch_content = read_novel_file(novel_name, "manuscript", f"{chapter_ref}.md")
    if not ch_content:
        return jsonify({"success": False, "error": f"章节不存在: {chapter_ref}"}), 404

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
    )

    if result["success"]:
        ch_id = chapter_ref.replace("/", "-").replace("ch-", "")
        # Sync structured review data to content.db
        try:
            from content_db import get_db as _cdb
            conn = _cdb()
            novel_row = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
            if novel_row:
                nid = novel_row["id"]
                # Extract binary contrast count from analyze stdout
                bc_match = __import__("re").search(r'binary_contrast_count:\s*(\d+)', analyze.get("stdout", ""))
                bc_count = int(bc_match.group(1)) if bc_match else 0
                jg_match = __import__("re").search(r'simple_judgment_groups:\s*(\d+)', analyze.get("stdout", ""))
                jg_count = int(jg_match.group(1)) if jg_match else 0
                tp_match = __import__("re").search(r'tell_patterns:\s*(\d+)', analyze.get("stdout", ""))
                tp_count = int(tp_match.group(1)) if tp_match else 0
                conn.execute("""INSERT INTO reviews (novel_id, chapter_ref, ai_review, script_detail,
                    wc_ok, compliance_ok, forbidden_ok, bcontrast_count, judgment_groups, tell_count, word_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(novel_id, chapter_ref, created_at) DO UPDATE SET
                    ai_review=excluded.ai_review, script_detail=excluded.script_detail,
                    wc_ok=excluded.wc_ok, compliance_ok=excluded.compliance_ok, forbidden_ok=excluded.forbidden_ok,
                    bcontrast_count=excluded.bcontrast_count, judgment_groups=excluded.judgment_groups, tell_count=excluded.tell_count""",
                    (nid, chapter_ref, result.get("content",""), analyze.get("stdout","") + "\n" + compliance.get("stdout","") + "\n" + forbidden.get("stdout",""),
                     1 if analyze.get("success") else 0, 1 if compliance.get("success") else 0, 1 if forbidden.get("success") else 0,
                     bc_count, jg_count, tp_count, count_words(ch_content)))
            conn.commit()
            conn.close()
        except Exception:
            pass
        review_content = f"""# 审稿报告

日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}
章节: {chapter_ref}

## AI审稿结果
{result['content']}

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

    return jsonify({
        "success": True,
        "ai_review": result.get("content", ""),
        "word_count": count_words(ch_content),
        "script_results": {
            "analyze": {"stdout": analyze.get("stdout", ""), "success": analyze.get("success", False)},
            "compliance": {"stdout": compliance.get("stdout", ""), "success": compliance.get("success", False)},
            "forbidden": {"stdout": forbidden.get("stdout", ""), "success": forbidden.get("success", False)},
        },
    })


@app.route("/api/novels/<novel_name>/optimize-chapter", methods=["POST"])
def api_optimize_chapter(novel_name):
    """One-click optimize: fix issues found during review"""
    data = request.json
    chapter_ref = data.get("chapter_ref", "")
    volume = data.get("volume", "vol-01")
    chapter_num = data.get("chapter_num", "")
    review_text = data.get("review_text", "")
    script_issues = data.get("script_issues", "")

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
    )

    if not result["success"]:
        return jsonify(result)

    # Backup original before overwriting
    bak_dir = os.path.join(get_novels_dir(), novel_name, "manuscript", ".bak")
    os.makedirs(bak_dir, exist_ok=True)
    ch_file = os.path.join(get_novels_dir(), novel_name, "manuscript", f"{chapter_ref}.md")
    if os.path.exists(ch_file):
        # Find next revision number
        rev = 1
        while os.path.exists(os.path.join(bak_dir, f"{chapter_ref.replace('/','-')}.rev{rev}.md")):
            rev += 1
        import shutil as _shutil
        _shutil.copy2(ch_file, os.path.join(bak_dir, f"{chapter_ref.replace('/','-')}.rev{rev}.md"))
        # Keep only last 5 versions
        bak_files = sorted([f for f in os.listdir(bak_dir) if chapter_ref.replace('/','-') in f])
        for old_f in bak_files[:-5]:
            os.remove(os.path.join(bak_dir, old_f))

    return jsonify({
        "success": True,
        "content": result["content"],
        "chapter_ref": chapter_ref,
        "word_count": count_words(result["content"]),
        "usage": result.get("usage", {}),
    })


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
    api_key = data.get("api_key", "").strip()
    api_base = data.get("api_base", "").strip()
    model = data.get("model", "").strip()
    temperature = str(data.get("temperature", "")).strip()
    max_tokens = str(data.get("max_tokens", "")).strip()
    top_p = str(data.get("top_p", "")).strip()

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

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "Hello, reply with exactly 'OK' if you can read this."}],
        "max_tokens": 10,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{cfg['api_base']}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                return jsonify({
                    "success": False,
                    "error": f"API错误 {resp.status_code}: {resp.text[:500]}",
                })
            data = resp.json()
            return jsonify({
                "success": True,
                "message": "✅ DeepSeek API 连接成功！",
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

    # --- AI type: call DeepSeek ---
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
            except Exception:
                pass

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
    conn = _sqlite3.connect(CONFIG_DB_PATH)
    conn.row_factory = _sqlite3.Row
    return conn

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
    if "error" in stats:
        return jsonify({"success": False, "error": stats["error"]}), 404
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


# ─── Start ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = get_active_deepseek_config()
    api_key_status = "已配置" if cfg["api_key"] else "未配置（可在设置页面配置）"
    config_source = "用户设置" if cfg["user_configured"] else "环境变量"
    print(f"\n{'='*60}")
    print(f"  小说写作 Agent Web Portal — NovelForge")
    print(f"{'='*60}")
    print(f"  📂 项目目录: {NOVEL_AGENT_ROOT}")
    print(f"  🤖 DeepSeek: {api_key_status} ({config_source})")
    print(f"  📡 API Base: {cfg['api_base']}")
    print(f"  🧠 模型: {cfg['model']}")
    print(f"  🌡️  温度: {cfg['temperature']} / MaxTokens: {cfg['max_tokens']} / TopP: {cfg['top_p']}")
    print(f"  🌐 访问地址: http://localhost:{PORTAL_PORT}")
    print(f"  ⚙️  设置页面可随时修改所有参数")
    print(f"{'='*60}\n")
    app.run(host=PORTAL_HOST, port=PORTAL_PORT, debug=DEBUG)
