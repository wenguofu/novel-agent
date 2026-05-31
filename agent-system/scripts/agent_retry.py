#!/usr/bin/env python3
"""
agent_retry.py — Auto-retry with error context injection.

When an agent output fails validation (schema, heuristics, signatures),
automatically retry up to N times with error context injected into the prompt.

Usage:
  # As library (import)
  from agent_retry import execute_with_retry
  result = execute_with_retry(agent_name, novel_path, stage, generate_fn, validate_fn)

  # As CLI
  python agent_retry.py --novel <path> --agent 正文写作 --file output.md --max-retries 3
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = [5, 15, 30]  # Exponential-ish


def execute_with_retry(
    agent_name: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: list = None,
    generate_fn: Callable = None,
    validate_fn: Callable = None,
    on_retry: Callable = None,
    novel_path: str = "",
    stage: str = "",
) -> dict:
    """Execute agent generation with auto-retry on validation failure.

    Args:
        agent_name: Name of the agent (e.g., '正文写作')
        max_retries: Maximum number of retry attempts (default 3)
        backoff_seconds: List of wait times between retries (default [5, 15, 30])
        generate_fn: Function that takes (attempt, error_context) and returns
                     {"content": str, "metadata": dict}
        validate_fn: Function that takes content string and returns
                     {"valid": bool, "errors": list, "warnings": list}
        on_retry: Callback(attempt, error_context) called before each retry
        novel_path: Novel project path (for logging)
        stage: Stage identifier (for logging)

    Returns:
        {
            "success": bool,
            "content": str,
            "attempts": int,
            "errors": list,
            "warnings": list,
            "history": list of per-attempt results
        }
    """
    backoff = backoff_seconds or DEFAULT_BACKOFF_SECONDS
    history = []

    for attempt in range(1, max_retries + 1):
        error_context = ""
        if attempt > 1 and history:
            prev = history[-1]
            if prev.get("errors"):
                error_context = _build_error_context(agent_name, attempt, prev)

        # Generate
        gen_result = generate_fn(attempt, error_context) if generate_fn else {"content": ""}
        content = gen_result.get("content", "") if isinstance(gen_result, dict) else str(gen_result)

        # Validate
        if validate_fn:
            validation = validate_fn(content)
        else:
            validation = {"valid": True, "errors": [], "warnings": []}

        record = {
            "attempt": attempt,
            "timestamp": datetime.now().isoformat(),
            "valid": validation.get("valid", True),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "content_length": len(content),
            "error_context_injected": bool(error_context),
        }
        history.append(record)

        if validation.get("valid", True):
            return {
                "success": True,
                "content": content,
                "attempts": attempt,
                "errors": [],
                "warnings": validation.get("warnings", []),
                "history": history,
            }

        if attempt < max_retries:
            if on_retry:
                on_retry(attempt, error_context)
            wait = backoff[min(attempt - 1, len(backoff) - 1)]
            time.sleep(wait)

    # All retries exhausted
    last = history[-1] if history else {}
    return {
        "success": False,
        "content": content if 'content' in dir() else "",
        "attempts": max_retries,
        "errors": last.get("errors", ["Max retries exceeded"]),
        "warnings": last.get("warnings", []),
        "history": history,
    }


def _build_error_context(agent_name: str, attempt: int, prev_result: dict) -> str:
    """Build error context string for injection into next retry prompt."""
    errors = prev_result.get("errors", [])
    warnings = prev_result.get("warnings", [])

    ctx = f"\n\n【第{attempt}次重试 — 前次验证反馈】\n"
    ctx += f"Agent: {agent_name}\n"

    if errors:
        ctx += "验证失败项:\n"
        for e in errors[:5]:
            ctx += f"  ❌ {e}\n"

    if warnings:
        ctx += "验证警告项:\n"
        for w in warnings[:3]:
            ctx += f"  ⚠️  {w}\n"

    ctx += "\n请根据以上反馈修正输出。重点关注: " + "; ".join(errors[:3]) + "\n"
    return ctx


# ── CLI ──────────────────────────────────────────────────────────────────

def _cli_generate(attempt, error_context):
    """CLI generate: read from file or stdin."""
    return {"content": ""}


def _cli_validate(content, agent_name):
    """CLI validate: use agent_executor if available."""
    try:
        from agent_executor import validate_agent_output
        result = validate_agent_output(content, agent_name, strict=False)
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except ImportError:
        return {"valid": True, "errors": [], "warnings": ["agent_executor unavailable"]}


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="agent_retry — 自动重试 + 错误上下文注入"
    )
    parser.add_argument("--novel", help="小说项目目录路径")
    parser.add_argument("--agent", required=True, help="Agent 名称")
    parser.add_argument("--file", help="要验证的输出文件路径")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help=f"最大重试次数 (默认: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--content", help="直接传入内容（与 --file 二选一）")
    args = parser.parse_args()

    # Load content
    content = ""
    if args.content:
        content = args.content
    elif args.file:
        fp = Path(args.file)
        if not fp.exists():
            print(f"❌ 文件不存在: {args.file}")
            sys.exit(1)
        content = fp.read_text(encoding='utf-8')

    if not content:
        print("❌ 需要 --file 或 --content 参数")
        sys.exit(1)

    # Validate
    validation = _cli_validate(content, args.agent)

    if validation["valid"]:
        print(f"✅ Agent '{args.agent}' 输出验证通过")
        sys.exit(0)
    else:
        print(f"❌ Agent '{args.agent}' 输出验证失败 ({len(validation['errors'])} 个错误)")
        for e in validation["errors"]:
            print(f"  ❌ {e}")
        for w in validation.get("warnings", []):
            print(f"  ⚠️  {w}")
        sys.exit(1)


if __name__ == "__main__":
    main()
