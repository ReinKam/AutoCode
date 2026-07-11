# AutoCode — why this exists, in one page

## The problem

AI coding agents (Claude Code, Cursor, Devin, and similar) are good at
*doing* work. None of them answer a different question that matters just
as much: **who decided this specific action was okay, under what rule,
and can you prove it after the fact?**

That gap is fine for a developer using an agent to help themselves. It
stops being fine the moment an organization wants an agent making
changes to a real codebase autonomously, over time, without a human
watching every keystroke.

## What AutoCode is

Not another coding agent. A **control plane** that sits in front of one
(or several): every action an agent proposes — write this file, run this
command — is evaluated by a deterministic policy engine before it's
allowed to happen. Most actions pass automatically. A defined few stop
and wait for a specific human to say yes.

> **The agent proposes. AutoCode decides. Nothing happens in between
> without a rule allowing it.**

— and every decision is logged in a way that can't be quietly edited
after the fact.

## What we just demonstrated (not just designed — ran)

We built the policy engine, then used it to govern a real, small
application getting built — a shared shopping-list app, multi-user,
built by an AI backend, live:

- **13 real build actions**, each evaluated by the same Policy Engine
  implementation that is covered by the golden test suite — not a
  simplified stand-in.
- **2 of them stopped** — both touching the app's user-identity logic —
  and waited for an actual human to approve, in real time.
- **Approval didn't just wave the action through.** It produced a fresh,
  independent decision, linked back to the one it resolved — proving the
  system re-checks itself rather than trusting a stale yes.
- **The resulting audit trail is tamper-evident.** We recomputed its
  integrity independently after the fact and confirmed nothing had been
  altered.
- **The application works.** Not just "the tests pass" — we ran it live,
  had one simulated user try to see another's list before joining
  (correctly refused), then join and share it (correctly allowed).

Everything above is reproducible with one command
(`bash run_all.sh`) from a fresh clone of this repository — we checked.

## What this is not, yet

A finished product. Today, a human (via this chat) played the role of
both the AI backend and the approver. The next real step is wiring in an
actual AI coding agent as the backend, so the loop runs without a person
standing in for it. Git operations, a real notification channel for
approvals, and a production-grade risk model are the steps after that.

## The point

Most of the value in "autonomous coding agents" gets sold on capability:
what can it build. AutoCode is a bet that the harder, more valuable
problem is **governance**: proving what an agent was and wasn't allowed
to do, and why. This MVP is small on purpose — small enough to fully
understand in one sitting, real enough to show that policy, human
approval, and audit trails aren't theoretical concerns bolted on later.
They're the thing that makes autonomous development trustworthy enough
to actually use.
