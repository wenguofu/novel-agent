#!/usr/bin/env bash
# check_tdd_compliance.sh — TDD physical gate for portal/ changes.
#
# Rules:
#   - portal/ changes must be accompanied by tests/ changes
#   - tests/ changes must be in test_*.py, conftest.py, __init__.py, fixtures/, audit/
#   - commit message containing "hotfix" bypasses the gate (env: HOOK_COMMIT_MSG_FILE)
#   - changes to the gate itself bypass
set -euo pipefail

# Hotfix bypass via commit message
COMMIT_MSG_FILE="${HOOK_COMMIT_MSG_FILE:-}"
if [ -n "$COMMIT_MSG_FILE" ] && [ -f "$COMMIT_MSG_FILE" ]; then
    if grep -qi "hotfix" "$COMMIT_MSG_FILE"; then
        echo "[check_tdd] hotfix detected in commit message — bypassing gate"
        exit 0
    fi
fi

# Detect staged changes
STAGED=$(git diff --cached --name-only)

# Handle empty staged changes (no files staged) — nothing to check, allow.
if [ -z "$STAGED" ]; then
    echo "[check_tdd] OK (no staged changes)"
    exit 0
fi

PORTAL_CHANGED=$(echo "$STAGED" | grep -E '^portal/.*\.py$' || true)
TESTS_CHANGED=$(echo "$STAGED" | grep -E '^tests/' || true)
SELF_CHANGED=$(echo "$STAGED" | grep -E '^(\.pre-commit-config\.yaml|scripts/check_tdd_compliance\.sh|\.claude/hooks/.*|agent-system/scripts/post_commit_review\.sh)$' || true)

# Self-change bypass (changing the gate itself is allowed)
if [ -n "$SELF_CHANGED" ] && [ -z "$PORTAL_CHANGED" ]; then
    echo "[check_tdd] only gate files changed — bypassing"
    exit 0
fi

# Rule 1: portal/ changes require tests/ changes
if [ -n "$PORTAL_CHANGED" ]; then
    if [ -z "$TESTS_CHANGED" ]; then
        echo "[check_tdd] BLOCK: portal/ changed but no tests/ changes" >&2
        echo "  Files changed:" >&2
        echo "$PORTAL_CHANGED" | sed 's/^/    /' >&2
        echo "  Fix: add or modify a file under tests/ in the same commit," >&2
        echo "       or include 'hotfix' in the commit message." >&2
        exit 1
    fi
fi

# Rule 2: tests/ changes must be in test_*.py or conftest.py
if [ -n "$TESTS_CHANGED" ]; then
    NON_TEST=$(echo "$TESTS_CHANGED" | grep -vE '^tests/(test_.*\.py|conftest\.py|.*/__init__\.py|.*/fixtures/.*|.*/audit/.*|test_check_tdd_compliance\.py)$' || true)
    if [ -n "$NON_TEST" ]; then
        echo "[check_tdd] BLOCK: tests/ contains non-test files" >&2
        echo "  Offenders:" >&2
        echo "$NON_TEST" | sed 's/^/    /' >&2
        echo "  Allowed: test_*.py, conftest.py, __init__.py, fixtures/, audit/" >&2
        exit 1
    fi
fi

echo "[check_tdd] OK"
exit 0
