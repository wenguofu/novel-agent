#!/usr/bin/env bash
# post_commit_review.sh — invokes the 6-dim agent code review.
# Args: $1 = full SHA (default: HEAD)
# Mode controlled by AGENT_CR_MODE env var: "stub" (placeholder) or "full" (default).
set -euo pipefail

SHA="${1:-$(git rev-parse HEAD)}"
SHORT_SHA="${SHA:0:7}"
REPORT_DIR=".code-reviews"
REPORT_FILE="$REPORT_DIR/$SHORT_SHA.md"

mkdir -p "$REPORT_DIR"

# Empty diff check
DIFF=$(git diff HEAD~1 HEAD 2>/dev/null || true)
if [ -z "$DIFF" ]; then
    echo "[agent-CR] empty diff — skipping"
    exit 0
fi

# Mode: stub or full (default full in M3.1)
MODE="${AGENT_CR_MODE:-full}"

if [ "$MODE" = "stub" ]; then
    # M3 stub mode — write placeholder
    {
        echo "# Agent Code Review — $SHORT_SHA"
        echo
        echo "**Commit:** \`$SHA\`"
        echo "**Date:** $(date -Iseconds)"
        echo "**Reviewer:** post_commit_review.sh (stub mode, 6-dim)"
        echo
        echo "## Summary"
        echo
        echo "- Total findings: **0**"
        echo "- Dimensions: 6 (stubbed)"
        echo
        echo "## Dimensions"
        echo
        for dim in Correctness Security Performance Tests Style Docs; do
            echo "### $dim — [STUB]"
            echo
            echo "_Stub mode — set AGENT_CR_MODE=full (default) to enable static analysis._"
            echo
        done
        echo "## ISSUES FOUND"
        echo
        echo "(stub mode — no analysis run)"
        echo
        echo "## VERDICT"
        echo
        echo "STUB"
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
    exit 0
fi

# Full mode — invoke Python orchestrator
if ! command -v python3 >/dev/null 2>&1; then
    echo "[agent-CR] python3 not found — falling back to stub"
    AGENT_CR_MODE=stub bash "$0" "$SHA"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Write diff to a temp file to avoid command-line / shell escaping issues
DIFF_TMP="$(mktemp -t agent_cr_diff.XXXXXX)"
trap 'rm -f "$DIFF_TMP"' EXIT
printf '%s' "$DIFF" > "$DIFF_TMP"

DATE_NOW="$(date -Iseconds)"

REPORT_BODY=$(python3 "$SCRIPT_DIR/agent_review_lib.py" "$SHA" "$DATE_NOW" "$DIFF_TMP" 2>&1) || {
    echo "[agent-CR] Python orchestrator failed — falling back to stub"
    AGENT_CR_MODE=stub bash "$0" "$SHA"
    exit 0
}

printf '%s\n' "$REPORT_BODY" > "$REPORT_FILE"

echo "[agent-CR] full report written to $REPORT_FILE"
