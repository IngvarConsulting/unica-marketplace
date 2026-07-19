# Marketplace Regression Policy Design

**Status:** approved for implementation on 2026-07-19 and revised to the
maintainer-approved `v0.7.6` bridge boundary.

## Context

Routine marketplace promotion, historical migration compatibility, and the
one-off duplicate registration from Unica issue #90 have different costs and
change rates. They must not share one automatic schedule.

Unica `v0.7.6` is the final package that understands old local and duplicated
installations. After it normalizes an installation, `v0.8.0` supports ordinary
updates from canonical `v0.7.5`, canonical `v0.7.6`, and canonical technical
`0.7.x` installations. Version alone is not proof of canonical identity.

## Policy

### Automatic pull-request and promotion checks

The marketplace exposes one stable aggregate job, `regression-policy`. It
requires only signals that can change during a normal promotion:

1. repository and manifest contracts;
2. staged package smoke on macOS, Linux, and Windows;
3. fresh consumer installation on all three systems;
4. exact candidate ref and source-release resolution;
5. previous-stable seed integrity;
6. canonical previous-stable update on all three systems.

Conditional jobs may be skipped only when the event does not require them.
Malformed event trees, catalog inputs, cache identity, or source releases fail
closed.

### Manual full-history regression

`Full legacy migration regression` has only `workflow_dispatch`. It resolves
the selected marketplace ref to an exact commit and builds a matrix from the
tracked release inventory.

Profile set `current` runs every supported legacy case and issue #90 once using
the current locked Codex CLI. Profile set `bridge` additionally runs only
`v0.3.11` and issue #90 on historical Codex CLI `0.144.1`; it does not multiply
the full matrix.

The manual workflow verifies exact source commits or asset digests, canonical
plugin identity, legacy cleanup, settings preservation, MCP and prompt
visibility, idempotence, and consumer-level rollback after an injected failure.

### Compatibility boundary

The full bridge regression is run against the promoted `v0.7.6` catalog before
issue #90 is closed. The resulting successful GitHub workflow run is release
evidence, not a receipt consumed by future promotions.

There is no weekly execution and no `0.9.x -> 1.x` barrier. Carrying that model
would contradict the decision to remove legacy migration in `v0.8.0`.

## Locked inputs

Codex release names and SHA-256 asset digests are tracked per supported system.
Published Unica archives are digest-locked where they exist; source-only
fixtures use exact tag commits. Candidate installers are resolved from the
published source release and verified by digest before execution.

## Test strategy

- unit tests validate manifests, profile selection, promotion event trees, and
  fail-closed behavior;
- workflow contract tests enforce manual-only full regression and the stable
  aggregate truth table;
- hosted jobs provide real macOS, Linux, and Windows consumer evidence;
- issue #90 remains a manual fixture, not an automatic promotion dependency.

## Delivery sequence

1. Merge this policy in marketplace PR #9.
2. Publish and promote source `v0.7.6`.
3. Run profile set `bridge` against the exact promoted catalog.
4. Close issue #90 using the successful workflow URL as evidence.
5. Keep automatic promotions bounded to fresh and previous-stable canonical
   paths while source issue #135 removes current legacy migration code.
