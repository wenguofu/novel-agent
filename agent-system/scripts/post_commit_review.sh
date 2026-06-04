#!/usr/bin/env bash
# post_commit_review.sh — invokes the 6-dim agent code review.
# Args: $1 = full SHA (default: HEAD)
# M3 ships in stub mode (writes a placeholder report). M3.1 wires the full agent.
set -euo pipefail

SHA="${1:-$(git rev-parse HEAD)}"
SHORT_SHA="${SHA:0:7}"
REPORT_DIR=".code-reviews"
REPORT_FILE="$REPORT_DIR/$SHORT_SHA.md"

mkdir -p "$REPORT_DIR"

DIFF=$(git diff HEAD~1 HEAD 2>/dev/null || true)
if [ -z "$DIFF" ]; then
    echo "[agent-CR] empty diff — skipping"
    exit 0
fi

# Write a placeholder report. M3.1 will invoke the actual agent.
{
    echo "# Agent Code Review — $SHORT_SHA"
    echo
    echo "**Commit:** \`$SHA\`"
    echo "**Date:** $(date -Iseconds)"
    echo "**Reviewer:** post_commit_review.sh (stub mode, 6-dim)"
    echo
    echo "## Dimensions"
    echo
    echo "1. Correctness    — ⏳ pending (M3.1 wires full agent)"
    echo "2. Security       — ⏳ pending"
    echo "3. Style          — ⏳ pending"
    echo "4. Test coverage  — ⏳ pending"
    echo "5. Performance    — ⏳ pending"
    echo "6. Docs           — ⏳ pending"
    echo
    echo "## ISSUES FOUND"
    echo
    echo "(pending — M3.1)"
    echo
    echo "## VERDICT"
    echo
    echo "STUB (M3.1 will populate)"
    echo
    echo "---"
    echo
    echo "<details><summary>Diff (for reference)</summary>"
    echo
    echo '```diff'
    echo "$DIFF"
    echo '```'
    echo
    echo "</details>"
} > "$REPORT_FILE"

echo "[agent-CR] stub report written to $REPORT_FILE"
