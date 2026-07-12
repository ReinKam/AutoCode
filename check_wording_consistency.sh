#!/usr/bin/env bash
# check_wording_consistency.sh
#
# Encodes one specific rule agreed on for this project's documentation:
#
#   "proves/proven/proving" is only acceptable when qualified by a
#   specific, tested claim (e.g. "proven by 56 golden tests", "the golden
#   test suite proves [this specific invariant]"). It is NOT acceptable
#   as an unqualified claim about the whole system or MVP.
#
# This script does not judge that distinction automatically — it finds
# every occurrence and prints surrounding context so a human (or Claude)
# can make the actual judgment call, the same way it was made manually
# across three separate rounds before this script existed. Run this
# BEFORE freezing/tagging any release, across ALL file types at once —
# not reactively, file by file, as issues get pointed out.

set -e
cd "$(dirname "$0")"

echo "Searching for 'prove/proves/proving/proven' across the whole repo..."
echo "(review each hit against the rule in this script's header comment)"
echo

grep -rniE "\bproves?\b|\bproving\b|\bproven\b" \
    --include="*.py" --include="*.md" --include="*.sh" \
    --include="*.json" --include="*.txt" \
    . 2>/dev/null | grep -v "\.git/" | grep -v "check_wording_consistency.sh" || \
    echo "No matches found."
