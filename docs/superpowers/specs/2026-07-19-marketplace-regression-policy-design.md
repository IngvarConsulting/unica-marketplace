# Marketplace Regression Policy Design

**Status:** approved for implementation on 2026-07-19

## Context

The marketplace currently combines three different responsibilities in the same
regression surface:

1. routine verification of a staged package and a normal marketplace promotion;
2. historical compatibility evidence for legacy `0.x` installations;
3. a one-off reproduction of the duplicate registration from Unica issue #90.

Running the complete historical matrix on a weekly schedule is not useful. It
repeats many equivalent legacy layouts even when neither Unica nor the
marketplace changed. Conversely, the current automatic workflow does not test
the normal previous-stable upgrade before a promotion is merged, and no single
stable check represents the complete promotion policy.

The transition to `1.0` also needs an explicit legacy-support boundary. Direct
legacy migration will end at the latest stable `0.9.x`, so that release line
must have durable full-history evidence before `1.0` can be promoted.

## Goals

- Keep routine promotion checks small, deterministic, and suitable for a
  required pull-request check.
- Keep full historical coverage available on demand without any scheduled run.
- Treat issue #90 as a historical fixture, not as a permanent promotion gate.
- Prove the normal previous-stable marketplace update before merge.
- Classify every published historical release instead of silently omitting
  releases that lack the expected archive shape.
- Create a machine-verifiable `0.9.x` barrier receipt that is required for the
  first `1.x` promotion.
- Pin the Codex CLI and published inputs used as regression evidence.

## Non-goals

- The marketplace will not continuously test every historical version.
- The issue #90 fixture will not run on ordinary pull requests or promotions.
- A pull request will not change repository branch-protection settings. It will
  expose a stable aggregate check that can be configured as required separately.
- Prerelease builds are not part of the supported migration contract unless a
  specific prerelease is explicitly retained as a transition fixture.

## Policy Layers

### Repository contract

Every pull request and push to `main` validates marketplace metadata, package
metadata, the promotion classifier, regression manifests, and workflow syntax.
Malformed or unavailable event commits fail closed.

### Staged package

When `plugins/unica` exists, its native bootstrap and MCP contract are tested on
macOS, Linux, and Windows. This checks the staged package bytes independently of
the catalog.

### Fresh installation

When the catalog and staged plugin versions match, Codex installs
`unica@unica` from the candidate catalog on all three operating systems and
verifies the installed bootstrap and MCP contract.

### Promotion upgrade

A semantic catalog `source.ref` change is a promotion. On both a promotion pull
request and a direct promotion push to `main`, the workflow must:

1. restore the exact previous-stable installation produced during the staging
   phase;
2. fail if the versioned seed is missing or does not match its recorded version,
   Codex profile, and seed schema;
3. update the marketplace to the exact candidate ref and commit;
4. perform the documented remove-and-add plugin update;
5. prove that exactly one expected version is installed and that the MCP
   bootstrap verifies on macOS, Linux, and Windows.

The promotion pull request is the blocking proof. Repeating the same check on a
direct `main` promotion is a safety net for unprotected or administrative
pushes, not a replacement for branch protection.

### Aggregate result

The workflow exposes one job named `regression-policy`. It always runs after the
conditional jobs and accepts a skipped result only when the event did not
require that job. On a promotion, a skipped or failed fresh-install,
previous-stable-upgrade, target-resolution, or barrier job fails the aggregate.

`regression-policy` is the check that repository settings should mark as
required after the workflow is merged into the default branch.

## Manual Full-History Regression

`Full legacy migration regression` is `workflow_dispatch` only. It has no
`schedule` and no implicit pull-request trigger.

The workflow resolves the selected marketplace branch or tag to an exact commit
and runs a manifest-driven matrix on macOS, Linux, and Windows. The manifest
classifies:

- every supported stable local-release state in `0.x`;
- stable tags such as `v0.3.4`, `v0.3.5`, and `v0.3.6` whose releases do not
  contain marketplace archives, rebuilt from their exact locked source tag
  commits;
- the retained marketplace transition state;
- the duplicate canonical/legacy issue #90 state;
- excluded prereleases together with a machine-readable exclusion reason.

No published release may disappear from the inventory without either a runnable
case or an explicit policy classification.

The manual workflow accepts a locked Codex profile set. At minimum the lock
contains the current policy CLI and the historical `0.144.1` CLI used by issue
#90. Normal full-history mode runs every case on the current policy CLI. Barrier
mode additionally runs the issue #90 fixture and its representative `v0.3.11`
legacy state on `0.144.1`; it does not multiply the entire historical matrix by
both CLI versions. The issue #90 fixture is never selected by the automatic
promotion workflow.

Each successful case proves the migrated version, canonical plugin identity,
legacy cleanup, settings preservation where applicable, doctor checks, MCP and
prompt visibility, absence of duplicate MCP registrations, and an idempotent
second run. A separate representative manual case injects a migration failure
and verifies consumer-level rollback.

## The `0.9.x` Legacy Barrier

The latest promoted stable `0.9.x` is the final direct-migration target for
legacy installations. If another `0.9.x` is promoted later, any older barrier
receipt becomes stale.

After the final `0.9.x` catalog is present at an exact marketplace commit, a
maintainer runs the complete manual regression from that same workflow ref. A
successful run emits a JSON receipt artifact containing:

- schema version;
- target Unica version and source release;
- exact marketplace workflow ref and commit;
- GitHub workflow run ID and URL;
- completion timestamp;
- regression-manifest digest;
- Codex profiles used;
- installer and locked-input digests.

The reviewed receipt is committed to the marketplace before the first `1.x`
promotion. The `1.x` promotion check validates that:

1. the previous stable catalog version is `0.9.x`;
2. the receipt targets that exact latest `0.9.x` version;
3. the recorded workflow is `Full legacy migration regression`, was dispatched
   manually, and completed successfully;
4. its head commit is the recorded marketplace commit and is an ancestor of the
   promotion base;
5. the catalog at that commit points at the recorded `0.9.x` release;
6. the manifest and required Codex-profile digests still match.

Missing, stale, malformed, or unverifiable evidence fails the `1.x` promotion.
The barrier is checked only at the legacy-support boundary; it is not rerun for
ordinary `1.x` patch promotions.

## Locked Inputs and Reproducibility

The Codex release tag alone is insufficient because release assets can be
replaced. A tracked lock records the release and SHA-256 digest for every Codex
asset used on each operating system. Historical Unica release assets are
verified against tracked digests where assets exist. Tag-based fixtures pin an
exact commit.

The candidate installer continues to be checked against published release
metadata, but the barrier receipt records the accepted installer digests so the
evidence remains meaningful after the run.

## Maintainability

Repeated Codex download, extraction, PATH isolation, and digest verification are
moved to one local composite action or helper. Platform definitions and legacy
release classifications live in data files rather than being copied across
jobs. The unused issue #90 download of the `v0.3.11` archive is removed.

Long-running consumer jobs receive explicit timeouts. The manual workflow uses a
concurrency group so two full runs for the same target and Codex profile cannot
consume duplicate runners simultaneously.

## Test Strategy

- Unit tests validate promotion and `0.9.x -> 1.x` boundary classification,
  malformed receipts, stale receipts, and exact event-tree selection.
- Manifest tests require every published release to have a runnable or excluded
  classification and validate all locked digests.
- Fixture tests cover each layout family, including issue #90.
- Workflow contract tests validate event triggers and the aggregate-result truth
  table without treating substring presence as runtime proof.
- `actionlint` validates workflow and expression syntax.
- Hosted macOS, Linux, and Windows jobs provide the consumer evidence that local
  unit tests cannot provide.

## Delivery Sequence

1. Merge this policy implementation while the catalog remains on `0.x`.
2. Configure `regression-policy` as a required check for `main`.
3. Continue normal staged-package and catalog-promotion releases through `0.9.x`.
4. Run and review the full manual regression against the final stable `0.9.x`.
5. Commit its verified barrier receipt.
6. Permit the first `1.x` promotion only after the barrier check passes.
