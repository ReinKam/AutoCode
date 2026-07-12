#!/usr/bin/env bash
# Runs the full AutoCode MVP test suite + demo, stopping on first failure.
set -e

cd "$(dirname "$0")"

echo "=== 1/5: precedence engine ==="
python3 tests/golden_test_suite.py
echo

echo "=== 2/5: rule matcher ==="
python3 tests/golden_test_suite_matcher.py
echo

echo "=== 3/5: canUseTool adapter ==="
python3 tests/golden_test_suite_adapter.py
echo

echo "=== 4/5: TTL + capability validation ==="
python3 tests/golden_test_suite_ttl.py
echo

echo "=== 5/5: end-to-end demo ==="
python3 demo/demo.py
echo

echo "All golden test suites passed and the demo ran cleanly."
