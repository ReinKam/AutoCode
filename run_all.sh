#!/usr/bin/env bash
# Single entrypoint: validates the AutoCode Policy Engine core, then validates
# the application it governed still works. Stops on first failure.
set -e

cd "$(dirname "$0")"

echo "############################################"
echo "# PART 1/2 — AutoCode core (golden tests + demo)"
echo "############################################"
bash autocode/run_all.sh
echo

echo "############################################"
echo "# PART 2/2 — listapp (the application AutoCode built)"
echo "############################################"
cd listapp && python3 tests/test_app.py
cd ..
echo

echo "Everything passed: the policy engine behaves as its golden tests"
echo "specify, and the application it governed into existence still works."
