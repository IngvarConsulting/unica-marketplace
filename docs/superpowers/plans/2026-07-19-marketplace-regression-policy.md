# Marketplace Regression Policy Implementation Plan

> **For agentic workers:** this is a historical execution record. Live code,
> tests, package metadata, and the approved design are authoritative.

**Status:** Historical; revised on 2026-07-19 after selecting `v0.7.6` as the
immutable migration bridge.

**Goal:** Make PR #9 provide bounded automatic promotion proof and a manual-only
full regression for the `v0.7.6` migration bridge.

## Implemented work units

1. Track the complete historical release inventory and locked Codex CLI assets.
2. Generate `current` and `bridge` manual matrices from that inventory.
3. Keep issue #90 and rollback in `workflow_dispatch` only.
4. Verify fresh installation and immediately previous stable canonical update
   automatically on macOS, Linux, and Windows.
5. Expose `regression-policy` as the stable aggregate check.
6. Resolve exact marketplace commits, published source releases, and installer
   SHA-256 digests before any hosted consumer run.

## Explicitly removed policy

The earlier draft proposed a receipt for a future final `0.9.x` release and a
special first-`1.x` promotion barrier. That proposal is superseded. It conflicts
with the approved source policy that freezes migration in `v0.7.6` and removes
the executable legacy implementation in `v0.8.0`.

There is no schedule, no receipt file, no `barrier_required` detector output,
and no receipt-verification job.

## Verification

```bash
PYTHONPATH=. python3 tests/test_regression_policy.py -v
PYTHONPATH=. python3 tests/test_detect_promotion.py -v
PYTHONPATH=. python3 tests/test_verify_marketplace.py -v
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
actionlint .github/workflows/*.yml .github/actions/setup-locked-codex/action.yml
git diff --check
```

Hosted proof is the PR #9 `Verify marketplace` run, followed after promotion by
the manually dispatched `Full legacy migration regression` against `v0.7.6`
with `profile_set=bridge`.
