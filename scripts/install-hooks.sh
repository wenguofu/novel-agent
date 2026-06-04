#!/usr/bin/env bash
# install-hooks.sh — install all project git hooks.
set -euo pipefail
HOOKS_DIR=".git/hooks"
mkdir -p "$HOOKS_DIR"

if [ -f .claude/hooks/post-commit ]; then
    cp .claude/hooks/post-commit "$HOOKS_DIR/post-commit"
    chmod +x "$HOOKS_DIR/post-commit"
    echo "[hooks] installed post-commit hook"
fi

if [ -f .pre-commit-config.yaml ]; then
    pre-commit install 2>/dev/null || echo "[hooks] pre-commit not installed; run: pip install pre-commit"
fi
