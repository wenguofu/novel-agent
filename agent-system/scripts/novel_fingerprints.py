#!/usr/bin/env python3
"""
Novel Fingerprints — incremental change detection for novel project files.

Maintains a state/.fingerprints.json per novel project. Each tracked file
gets an MD5 hash + metadata. Subsequent runs compare hashes to detect
what changed, enabling targeted re-validation instead of full re-runs.

Usage:
  python novel_fingerprints.py --novel <path> build        # Full fingerprint scan
  python novel_fingerprints.py --novel <path> check        # Exit 0 if unchanged, 1 if changed
  python novel_fingerprints.py --novel <path> check --json # JSON list of changed files
  python novel_fingerprints.py --novel <path> update --file <relpath>  # Update single file
  python novel_fingerprints.py --novel <path> diff          # Show what changed since last build
  python novel_fingerprints.py --novel <path> status        # Quick summary
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


FINGERPRINTS_FILE = ".fingerprints.json"
STATE_DIR = "state"

# Files to track for fingerprinting
DEFAULT_TRACK_PATTERNS = [
    "project.md",
    "characters.md",
    "genre_bible.md",
    "world_bible.md",
    "full_story_arc.md",
    "alias_registry.md",
    "volume_plan.md",
    "current_status.md",
    "manuscript/**/*.md",
    "outline/**/*.md",
    "reviews/**/*.md",
    "state/current_status.md",
    "volume_plan/**/*.md",
]


def _compute_hash(filepath: Path) -> str:
    """Compute MD5 hash of a file's content."""
    if not filepath.exists():
        return ""
    try:
        return hashlib.md5(filepath.read_bytes()).hexdigest()
    except (IOError, OSError):
        return ""


def _get_mtime(filepath: Path) -> str:
    """Get file modification time as ISO string."""
    if not filepath.exists():
        return ""
    try:
        return datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
    except (IOError, OSError):
        return ""


def _get_size(filepath: Path) -> int:
    """Get file size in bytes."""
    if not filepath.exists():
        return 0
    try:
        return filepath.stat().st_size
    except (IOError, OSError):
        return 0


def _resolve_tracked_files(novel_path: Path) -> list[str]:
    """Resolve glob patterns to actual file paths (relative to novel_path)."""
    result = []
    for pattern in DEFAULT_TRACK_PATTERNS:
        if '**' in pattern or '*' in pattern:
            matches = sorted(novel_path.glob(pattern))
            for m in matches:
                if m.is_file():
                    rel = str(m.relative_to(novel_path))
                    if rel not in result:
                        result.append(rel)
        else:
            # Direct file — check existence
            fp = novel_path / pattern
            if fp.is_file():
                rel = pattern
                if rel not in result:
                    result.append(rel)
    return result


def load_fingerprints(novel_path: Path) -> dict:
    """Load existing fingerprint data, or return empty dict."""
    fp_file = novel_path / STATE_DIR / FINGERPRINTS_FILE
    if not fp_file.exists():
        return {"version": 2, "novel": novel_path.name, "fingerprints": {}}
    try:
        return json.loads(fp_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, IOError):
        return {"version": 2, "novel": novel_path.name, "fingerprints": {}}


def save_fingerprints(novel_path: Path, data: dict):
    """Save fingerprint data to the state directory."""
    state_dir = novel_path / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    fp_file = state_dir / FINGERPRINTS_FILE
    data["updated_at"] = datetime.now().isoformat()
    fp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_build(novel_path: Path):
    """Build full fingerprint set for all tracked files."""
    tracked = _resolve_tracked_files(novel_path)
    data = load_fingerprints(novel_path)
    data["novel"] = novel_path.name

    fingerprints = {}
    for relpath in tracked:
        fp = novel_path / relpath
        fingerprints[relpath] = {
            "hash": _compute_hash(fp),
            "size": _get_size(fp),
            "mtime": _get_mtime(fp),
        }

    data["fingerprints"] = fingerprints
    data["tracked_count"] = len(fingerprints)
    save_fingerprints(novel_path, data)

    print(f"✅ 指纹构建完成: {len(fingerprints)} 个文件已追踪")
    return 0


def cmd_check(novel_path: Path, json_output: bool = False) -> int:
    """Check which files have changed since last fingerprint build."""
    data = load_fingerprints(novel_path)
    stored = data.get("fingerprints", {})
    changed = []
    missing = []
    new_files = []

    tracked = _resolve_tracked_files(novel_path)

    for relpath in tracked:
        fp = novel_path / relpath
        current_hash = _compute_hash(fp)

        if relpath not in stored:
            if current_hash:
                new_files.append(relpath)
        else:
            stored_hash = stored[relpath].get("hash", "")
            if current_hash != stored_hash:
                if current_hash:
                    changed.append(relpath)
                else:
                    missing.append(relpath)

    # Also detect deleted files
    for relpath in stored:
        if relpath not in tracked:
            missing.append(relpath)

    has_changes = bool(changed or missing or new_files)

    if json_output:
        result = {
            "changed": changed,
            "missing": missing,
            "new": new_files,
            "has_changes": has_changes,
            "total_tracked": len(tracked),
            "total_stored": len(stored),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not has_changes:
            print(f"✅ 无变化 — {len(tracked)} 个文件均为最新")
        else:
            for f in changed:
                print(f"  ✏️  变更: {f}")
            for f in new_files:
                print(f"  ✨ 新增: {f}")
            for f in missing:
                print(f"  ❌ 缺失: {f}")
            print(f"\n📊 总计: {len(changed)} 变更, {len(new_files)} 新增, {len(missing)} 缺失")

    return 1 if has_changes else 0


def cmd_update(novel_path: Path, relpath: str):
    """Update fingerprint for a single file."""
    fp = novel_path / relpath
    data = load_fingerprints(novel_path)

    if not fp.exists():
        print(f"⚠️  文件不存在: {relpath} (从指纹中移除)")
        data["fingerprints"].pop(relpath, None)
    else:
        data["fingerprints"][relpath] = {
            "hash": _compute_hash(fp),
            "size": _get_size(fp),
            "mtime": _get_mtime(fp),
        }
        print(f"✅ 已更新: {relpath}")

    save_fingerprints(novel_path, data)
    return 0


def cmd_diff(novel_path: Path):
    """Show detailed diff of what changed in each modified file."""
    data = load_fingerprints(novel_path)
    stored = data.get("fingerprints", {})

    for relpath, info in sorted(stored.items()):
        fp = novel_path / relpath
        current_hash = _compute_hash(fp)
        stored_hash = info.get("hash", "")

        if current_hash != stored_hash:
            old_size = info.get("size", 0)
            new_size = _get_size(fp)
            delta = new_size - old_size
            sign = "+" if delta > 0 else ""
            print(f"  {relpath}: {old_size} → {new_size} bytes ({sign}{delta})")

    return 0


def cmd_status(novel_path: Path):
    """Print a quick summary of the fingerprint state."""
    data = load_fingerprints(novel_path)
    stored = data.get("fingerprints", {})
    tracked = _resolve_tracked_files(novel_path)

    print(f"📖 {data.get('novel', novel_path.name)}")
    print(f"   已追踪: {len(stored)} 个文件")
    print(f"   当前可追踪: {len(tracked)} 个文件")
    print(f"   最后更新: {data.get('updated_at', '从未')}")

    # Count by directory
    from collections import Counter
    dirs = Counter()
    for relpath in tracked:
        d = str(Path(relpath).parent)
        dirs[d] += 1

    print(f"\n   按目录分布:")
    for d, count in dirs.most_common(8):
        print(f"     {d}: {count} 文件")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="novel_fingerprints — 小说项目增量变更检测"
    )
    parser.add_argument("--novel", required=True, help="小说项目目录路径")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["build", "check", "update", "diff", "status"])
    parser.add_argument("--file", help="update 命令的文件相对路径")
    parser.add_argument("--json", action="store_true", help="check 命令输出 JSON 格式")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    novel_path = Path(args.novel).resolve()

    if not novel_path.exists():
        print(f"❌ 小说目录不存在: {novel_path}")
        sys.exit(1)

    cmd = args.command

    if cmd == "build":
        sys.exit(cmd_build(novel_path))
    elif cmd == "check":
        sys.exit(cmd_check(novel_path, json_output=args.json))
    elif cmd == "update":
        if not args.file:
            print("❌ update 需要 --file 参数")
            sys.exit(1)
        sys.exit(cmd_update(novel_path, args.file))
    elif cmd == "diff":
        sys.exit(cmd_diff(novel_path))
    elif cmd == "status":
        sys.exit(cmd_status(novel_path))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
