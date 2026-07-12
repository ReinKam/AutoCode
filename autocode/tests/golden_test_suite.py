"""
Golden test suite for the AutoCode Policy Engine precedence function.

This is the executable specification of the precedence algorithm.
Every scenario here must produce the exact same `decision` and
`reason_code` on every run, on every machine, forever (for a given
policy_ruleset_version) — that IS the determinism claim.

Run: python3 golden_test_suite.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "policy_engine"))
from precedence import Effect, MatchedRule, HilApproval, resolve  # noqa: E402


# --- Reference ruleset fixtures (mirrors ruleset.schema.json examples) -----

AUTH_CHANGES_REQUIRE_HIL = MatchedRule(
    rule_id="AUTH_CHANGES_REQUIRE_HIL",
    effect=Effect.require_hil,
    approvable=True,
    required_approver_roles=("security_reviewer",),
)

DELETE_AUDIT_LOG = MatchedRule(
    rule_id="DELETE_AUDIT_LOG",
    effect=Effect.deny_permanent,
    approvable=False,
    required_approver_roles=(),
)

PUSH_MAIN_REQUIRES_HIL = MatchedRule(
    rule_id="NO_PUSH_MAIN_WITHOUT_HIL",
    effect=Effect.require_hil,
    approvable=True,
    required_approver_roles=("owner",),
)


def sec_reviewer_approval(targets=()):
    return HilApproval(
        hil_decision_id="hil-001",
        status="approved",
        approver_role="security_reviewer",
        targets_rule_ids=targets,
    )


def owner_approval(targets=()):
    return HilApproval(
        hil_decision_id="hil-002",
        status="approved",
        approver_role="owner",
        targets_rule_ids=targets,
    )


def sec_reviewer_rejection(targets=()):
    return HilApproval(
        hil_decision_id="hil-003",
        status="rejected",
        approver_role="security_reviewer",
        targets_rule_ids=targets,
    )


# --- Golden cases ------------------------------------------------------

CASES = []


def case(name, matched_rules, hil_decisions, risk_tier, expect_decision, expect_reason):
    CASES.append(dict(
        name=name,
        matched_rules=matched_rules,
        hil_decisions=hil_decisions,
        risk_tier=risk_tier,
        expect_decision=expect_decision,
        expect_reason=expect_reason,
    ))


case(
    name="auth-endring uten HIL -> require_hil",
    matched_rules=[AUTH_CHANGES_REQUIRE_HIL],
    hil_decisions=[],
    risk_tier="high",
    expect_decision=Effect.require_hil,
    expect_reason="REQUIRES_HUMAN_APPROVAL",
)

case(
    name="audit-log-sletting -> deny_permanent (aldri overstyrbar)",
    matched_rules=[DELETE_AUDIT_LOG],
    hil_decisions=[owner_approval()],  # even an approval attempt must not help
    risk_tier="critical",
    expect_decision=Effect.deny_permanent,
    expect_reason="PERMANENTLY_DENIED",
)

case(
    name="HIL approved auth-endring -> allow",
    matched_rules=[AUTH_CHANGES_REQUIRE_HIL],
    hil_decisions=[sec_reviewer_approval(targets=("AUTH_CHANGES_REQUIRE_HIL",))],
    risk_tier="high",
    expect_decision=Effect.allow,
    expect_reason="HIL_APPROVED_HIGH_RISK_ACTION",
)

case(
    name="HIL rejected auth-endring -> deny_until_changed",
    matched_rules=[AUTH_CHANGES_REQUIRE_HIL],
    hil_decisions=[sec_reviewer_rejection(targets=("AUTH_CHANGES_REQUIRE_HIL",))],
    risk_tier="high",
    expect_decision=Effect.deny_until_changed,
    expect_reason="HIL_REJECTED",
)

case(
    name="unknown risk -> require_hil (strukturell garanti, uavhengig av matched_rules)",
    matched_rules=[],  # deliberately empty: guarantee must not depend on rules
    hil_decisions=[],
    risk_tier="unknown",
    expect_decision=Effect.require_hil,
    expect_reason="UNKNOWN_RISK_TIER",
)

case(
    name="push main uten HIL -> require_hil",
    matched_rules=[PUSH_MAIN_REQUIRES_HIL],
    hil_decisions=[],
    risk_tier="medium",
    expect_decision=Effect.require_hil,
    expect_reason="REQUIRES_HUMAN_APPROVAL",
)

case(
    name="push main med gyldig HIL (owner) -> allow",
    matched_rules=[PUSH_MAIN_REQUIRES_HIL],
    hil_decisions=[owner_approval(targets=("NO_PUSH_MAIN_WITHOUT_HIL",))],
    risk_tier="medium",
    expect_decision=Effect.allow,
    expect_reason="HIL_APPROVED_HIGH_RISK_ACTION",
)

# --- Extra edge cases worth locking in now, cheaply ---------------------

case(
    name="feil godkjenner-rolle kan ikke overstyre (owner godkjenner auth-regel som krever security_reviewer)",
    matched_rules=[AUTH_CHANGES_REQUIRE_HIL],
    hil_decisions=[owner_approval(targets=("AUTH_CHANGES_REQUIRE_HIL",))],
    risk_tier="high",
    expect_decision=Effect.require_hil,
    expect_reason="REQUIRES_HUMAN_APPROVAL",
)

case(
    name="deny_permanent vinner selv sammen med en allow-rule i samme evaluering",
    matched_rules=[
        DELETE_AUDIT_LOG,
        MatchedRule("SOME_LOW_RISK_RULE", Effect.allow, False, ()),
    ],
    hil_decisions=[],
    risk_tier="critical",
    expect_decision=Effect.deny_permanent,
    expect_reason="PERMANENTLY_DENIED",
)

case(
    name="require_hil og deny_permanent samtidig -> deny_permanent vinner (strengeste effekt)",
    matched_rules=[AUTH_CHANGES_REQUIRE_HIL, DELETE_AUDIT_LOG],
    hil_decisions=[sec_reviewer_approval(targets=("AUTH_CHANGES_REQUIRE_HIL",))],
    risk_tier="critical",
    expect_decision=Effect.deny_permanent,
    expect_reason="PERMANENTLY_DENIED",
)

case(
    name="ingen regler matcher -> require_hil (MVP fail-closed default, ikke lenger allow)",
    matched_rules=[],
    hil_decisions=[],
    risk_tier="medium",
    expect_decision=Effect.require_hil,
    expect_reason="NO_RULES_MATCHED",
)


def run():
    failures = []
    for c in CASES:
        result = resolve(
            matched_rules=c["matched_rules"],
            hil_decisions=c["hil_decisions"],
            risk_tier=c["risk_tier"],
        )
        ok = result.decision == c["expect_decision"] and result.reason_code == c["expect_reason"]
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {c['name']}")
        print(f"       -> decision={result.decision.name} reason={result.reason_code}")
        if not ok:
            print(f"       expected: decision={c['expect_decision'].name} reason={c['expect_reason']}")
            failures.append(c["name"])

    print()
    if failures:
        print(f"{len(failures)} of {len(CASES)} golden cases FAILED:")
        for name in failures:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print(f"All {len(CASES)} golden cases passed. Precedence resolution is deterministic for these scenarios.")


if __name__ == "__main__":
    run()
