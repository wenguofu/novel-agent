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
                                if "content" in delta:
                                    full_text.append(delta["content"])
                                    yield f"data: {json.dumps({'type': 'token', 'content': delta['content']})}\n\n"
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

    system_prompt = f"""你是一个专业的长篇网文写作Agent。你的任务是严格按照项目资料和大纲，写出高质量的小说章节。

## 写作约束
1. 严格遵守类型规则和世界观设定
2. 人物行为必须符合人物档案
3. 不得使用真实地名、人名（使用虚构别名）
4. 每章正文纯字数不少于2500字
5. 不得使用'不是...而是...'二元对照句式超过2次
6. 必须有明确的章节功能和结尾牵引

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
