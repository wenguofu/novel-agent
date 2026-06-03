#!/usr/bin/env bash
# measure_coverage.sh — runs the full suite with coverage, enforces ≥ 90%.
# CI-only. Pre-commit does NOT run this (too slow for every commit).
set -euo pipefail

MIN_COVERAGE=90
REPORT=$(python3 -m pytest tests/ --cov=portal --cov-report=term --cov-report=json:/tmp/cov.json -q 2>&1) || true
echo "$REPORT" | tail -20

COVERAGE=$(echo "$REPORT" | grep -oE 'TOTAL\s+[0-9]+\s+[0-9]+\s+[0-9]+%' | awk '{print $4}' | tr -d '%')

if [ -z "$COVERAGE" ]; then
    echo "[coverage] FAIL: could not parse coverage %" >&2
    exit 1
fi

if [ "$COVERAGE" -lt "$MIN_COVERAGE" ]; then
    echo "[coverage] FAIL: $COVERAGE% < required $MIN_COVERAGE%" >&2
    echo "Run 'python3 -m pytest tests/ --cov=portal --cov-report=term-missing' to see gaps." >&2
    exit 1
fi

echo "[coverage] OK: $COVERAGE% ≥ $MIN_COVERAGE%"
exit 0
