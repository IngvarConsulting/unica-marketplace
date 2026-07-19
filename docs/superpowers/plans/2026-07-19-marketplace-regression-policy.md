# Marketplace Regression Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PR #9 provide a compact promotion gate, a manual-only full historical regression, and a verifiable final-`0.9.x` legacy barrier.

**Architecture:** Put release and Codex compatibility data in validated JSON contracts, keep event classification and barrier validation in testable Python, and leave hosted workflows responsible only for orchestration and consumer proof. A single `regression-policy` job evaluates conditional job results and becomes the required branch check.

**Tech Stack:** Python 3.12 standard library, GitHub Actions YAML, PowerShell 7/Windows PowerShell, Codex CLI plugin commands, JSON contracts, `unittest`, `actionlint`.

## Global Constraints

- `Full legacy migration regression` is `workflow_dispatch` only; it has no schedule.
- Issue #90 runs only in the manual full-history matrix.
- Automatic promotion tests fresh install and previous-stable update on macOS, Linux, and Windows using the current locked Codex CLI.
- Barrier mode runs the complete current-CLI matrix plus only `v0.3.11` and issue #90 on historical Codex `0.144.1`.
- The first `1.x` promotion requires a successful receipt for the exact latest promoted stable `0.9.x`.
- Malformed event trees, manifests, locks, caches, and receipts fail closed.
- Fix duplicated workflow mechanics only where the policy uses them.

---

### Task 1: Regression Contract Model

**Files:**
- Create: `.github/contracts/codex-cli-lock.json`
- Create: `.github/contracts/legacy-releases.json`
- Create: `scripts/regression_policy.py`
- Create: `tests/test_regression_policy.py`

**Interfaces:**
- Produces: `load_codex_lock(path) -> dict`, `load_release_inventory(path) -> dict`, `build_manual_cases(inventory, profile_set) -> list[dict]`, `requires_legacy_barrier(previous_version, target_version) -> bool`.
- Produces CLI: `python3 scripts/regression_policy.py matrix --profile-set current|barrier --github-output PATH`.

- [ ] **Step 1: Write failing manifest and boundary tests**

```python
def test_full_inventory_classifies_every_published_release(self):
    inventory = policy.load_release_inventory(RELEASES)
    self.assertEqual(inventory["schemaVersion"], 1)
    for version in ("0.3.3", "0.3.4", "0.3.5", "0.3.6", "0.3.10",
                    "0.3.11", "0.3.12", "0.4.1", "0.4.2", "0.4.3",
                    "0.4.4", "0.5.1", "0.6.1", "0.7.0", "0.7.1",
                    "0.7.2", "0.7.4"):
        self.assertIn(version, {entry["version"] for entry in inventory["releases"]})

def test_barrier_mode_does_not_double_the_full_matrix(self):
    cases = policy.build_manual_cases(policy.load_release_inventory(RELEASES), "barrier")
    historical = [case["label"] for case in cases if case["codexProfile"] == "historical-0.144.1"]
    self.assertEqual(historical, ["v0.3.11", "issue-90-duplicate"])

def test_only_zero_to_one_transition_requires_barrier(self):
    self.assertTrue(policy.requires_legacy_barrier("0.9.8", "1.0.0"))
    self.assertFalse(policy.requires_legacy_barrier("0.9.7", "0.9.8"))
    self.assertFalse(policy.requires_legacy_barrier("1.0.0", "1.0.1"))
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.test_regression_policy -v`

Expected: import/file-not-found failures for `scripts.regression_policy` and the contract files.

- [ ] **Step 3: Add validated data contracts and minimal Python model**

The Codex lock contains profiles `current` (`rust-v0.145.0-alpha.18`) and `historical-0.144.1` (`rust-v0.144.1`) with exact asset names and 64-character SHA-256 values for `darwin-arm64`, `linux-x64`, and `win-x64`.

The release inventory uses `classification: supported|transition|excluded`, exact tag commits for `v0.3.4`-`v0.3.6`, and `reason` for every excluded prerelease. It has a separate `fixtures` entry for issue #90.

```python
def requires_legacy_barrier(previous_version: str, target_version: str) -> bool:
    previous = tuple(map(int, previous_version.split(".")))
    target = tuple(map(int, target_version.split(".")))
    return previous[0] == 0 and previous[1] == 9 and target[0] == 1

def build_manual_cases(inventory: dict, profile_set: str) -> list[dict]:
    cases = [case_for(entry, "current") for entry in inventory["releases"]
             if entry["classification"] in {"supported", "transition"}]
    cases.extend(case_for(entry, "current") for entry in inventory["fixtures"])
    if profile_set == "barrier":
        selected = [entry for entry in inventory["releases"] if entry["version"] == "0.3.11"]
        selected.extend(inventory["fixtures"])
        cases.extend(case_for(entry, "historical-0.144.1") for entry in selected)
    return cases
```

- [ ] **Step 4: Run RED tests to GREEN**

Run: `python3 -m unittest tests.test_regression_policy -v`

Expected: all regression-policy tests pass.

- [ ] **Step 5: Commit**

```bash
git add .github/contracts scripts/regression_policy.py tests/test_regression_policy.py
git commit -m "test: define marketplace regression contracts"
```

### Task 2: Manual-Only Full Regression

**Files:**
- Modify: `.github/workflows/legacy-migration-regression.yml`
- Modify: `.github/workflows/legacy-migration-case.yml`
- Modify: `scripts/legacy_migration_fixture.py`
- Modify: `tests/test_legacy_migration_fixture.py`
- Modify: `tests/test_verify_marketplace.py`

**Interfaces:**
- Consumes: `matrix` output from `scripts/regression_policy.py`.
- Produces: manual current/barrier profile matrices and evidence artifacts.

- [ ] **Step 1: Write failing workflow-policy tests**

```python
def test_full_regression_is_manual_only(self):
    workflow = FULL_WORKFLOW.read_text(encoding="utf-8")
    self.assertIn("workflow_dispatch:", workflow)
    self.assertNotIn("schedule:", workflow)
    self.assertNotIn("pull_request:", workflow)

def test_issue_90_is_absent_from_automatic_workflow(self):
    automatic = VERIFY_WORKFLOW.read_text(encoding="utf-8")
    self.assertNotIn("issue-90-duplicate", automatic)
    self.assertNotIn("legacy-stable-upgrade:", automatic)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_verify_marketplace -v`

Expected: failure because `schedule:` and `legacy-stable-upgrade` still exist.

- [ ] **Step 3: Make the workflow consume the manifest matrix**

Add `profile_set` choice input with `current` and `barrier`, emit compact JSON from `resolve-target`, and use:

```yaml
strategy:
  fail-fast: false
  matrix:
    source: ${{ fromJSON(needs.resolve-target.outputs.source_matrix) }}
uses: ./.github/workflows/legacy-migration-case.yml
with:
  codex_profile: ${{ matrix.source.codexProfile }}
```

Remove the schedule, the hard-coded source matrix, and the unused `v0.3.11` download. Add `source-tag` handling by cloning `IngvarConsulting/unica`, checking out the exact locked commit, and archiving that tree locally before fixture creation.

Add one `manual-rollback` job on the three operating systems. It builds the
representative previous-stable fixture, runs the candidate installer with a
test-only unreachable runtime source, requires a non-zero exit, and compares
the saved `config.toml`, marketplace roots, plugin caches, and file permissions
with their pre-migration SHA-256/metadata snapshot. This job is manual-only and
is required before `barrier-receipt` can run.

- [ ] **Step 4: Run tests to GREEN**

Run: `python3 -m unittest tests.test_verify_marketplace tests.test_legacy_migration_fixture -v`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/legacy-migration-regression.yml .github/workflows/legacy-migration-case.yml scripts/legacy_migration_fixture.py tests
git commit -m "ci: make full migration regression manual only"
```

### Task 3: Locked Codex Setup

**Files:**
- Create: `.github/actions/setup-locked-codex/action.yml`
- Modify: `.github/workflows/legacy-migration-case.yml`
- Modify: `.github/workflows/verify.yml`
- Modify: `tests/test_verify_marketplace.py`

**Interfaces:**
- Consumes: `profile`, `target`, `asset-name`, `executable-name`, `codex-home`.
- Produces: `CODEX_BIN`, `CODEX_BIN_DIR`, and a verified native executable.

- [ ] **Step 1: Add a failing structural contract test**

```python
def test_workflows_use_one_locked_codex_setup(self):
    workflows = "\n".join(path.read_text() for path in WORKFLOWS)
    self.assertNotIn("gh release download rust-v0.145.0-alpha.18", workflows)
    self.assertIn("uses: ./.github/actions/setup-locked-codex", workflows)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_verify_marketplace -v`

Expected: the hard-coded downloader assertion fails.

- [ ] **Step 3: Implement the composite action**

The PowerShell composite step reads the selected profile from
`.github/contracts/codex-cli-lock.json`, requires an exact release and asset,
downloads it with `gh release download`, compares `Get-FileHash -Algorithm
SHA256`, extracts it, and writes `CODEX_BIN`/`CODEX_BIN_DIR` to `GITHUB_ENV`.
Replace all five downloader copies with the action.

- [ ] **Step 4: Verify GREEN and syntax**

Run: `python3 -m unittest tests.test_verify_marketplace -v`

Run: `actionlint .github/workflows/*.yml .github/actions/setup-locked-codex/action.yml`

Expected: tests and actionlint pass.

- [ ] **Step 5: Commit**

```bash
git add .github/actions .github/workflows tests/test_verify_marketplace.py
git commit -m "ci: verify Codex CLI from a locked profile"
```

### Task 4: Pre-Merge Previous-Stable Gate and Aggregate Check

**Files:**
- Modify: `.github/workflows/verify.yml`
- Modify: `scripts/detect_promotion.py`
- Modify: `tests/test_detect_promotion.py`
- Modify: `tests/test_verify_marketplace.py`

**Interfaces:**
- Produces detector outputs `promotion_required`, `seed_required`, and `barrier_required`.
- Produces stable job `regression-policy`.

- [ ] **Step 1: Add failing event and truth-table tests**

```python
def test_promotion_pr_requires_previous_stable_upgrade(self):
    result = detect_pr(base_catalog="v0.7.5", head_catalog="v0.7.6", plugin="0.7.6")
    self.assertEqual(result["promotion_required"], "true")

def test_regression_policy_requires_upgrade_on_promotion(self):
    workflow = VERIFY_WORKFLOW.read_text(encoding="utf-8")
    self.assertIn("github.event_name == 'pull_request'", previous_stable_job(workflow))
    self.assertIn("regression-policy:", workflow)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_detect_promotion tests.test_verify_marketplace -v`

Expected: missing outputs and PR condition failures.

- [ ] **Step 3: Implement exact conditions**

Version the seed key as `unica-upgrade-v2-${target}-${codex_profile}-${catalog_version}`. Validate `plugin list` after restore before mutation. Permit previous-stable-upgrade for both promotion PR and promotion `main` push. Add an always-running aggregate job whose PowerShell truth table rejects skipped required jobs and failed non-skipped jobs.

```yaml
regression-policy:
  if: always()
  needs: [contract, resolve-migration-target, staged-package-smoke,
          consumer-fresh-install, previous-stable-seed,
          previous-stable-upgrade, verify-legacy-barrier]
```

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_detect_promotion tests.test_verify_marketplace -v`

Expected: all tests pass, including the aggregate truth table.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/verify.yml scripts/detect_promotion.py tests
git commit -m "ci: gate promotions on previous stable updates"
```

### Task 5: `0.9.x` Barrier Receipt

**Files:**
- Create: `scripts/legacy_barrier.py`
- Create: `tests/test_legacy_barrier.py`
- Modify: `.github/workflows/legacy-migration-regression.yml`
- Modify: `.github/workflows/verify.yml`
- Modify: `tests/test_verify_marketplace.py`

**Interfaces:**
- Produces: `create_receipt(...) -> dict`, `validate_receipt(receipt, previous_version, run, catalog_version, is_ancestor) -> list[str]`.
- Produces CLI subcommands `create` and `verify`.

- [ ] **Step 1: Write failing receipt tests**

```python
def test_receipt_must_match_latest_zero_nine(self):
    errors = validate_receipt(valid_receipt("0.9.7"), "0.9.8", successful_run(), "0.9.7", True)
    self.assertIn("receipt target 0.9.7 != previous stable 0.9.8", errors)

def test_successful_exact_run_is_accepted(self):
    self.assertEqual(validate_receipt(valid_receipt("0.9.8"), "0.9.8",
                                      successful_run(), "0.9.8", True), [])
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_legacy_barrier -v`

Expected: import failure for `scripts.legacy_barrier`.

- [ ] **Step 3: Implement receipt generation and verification**

The manual workflow adds `barrier-receipt` after the full matrix. It runs only
for `profile_set == 'barrier'` and target `0.9.x`, calls `legacy_barrier.py
create`, and uploads `legacy-migration-barrier.json`.

The automatic workflow adds `verify-legacy-barrier` only when detector output
`barrier_required == true`. It reads the committed receipt, obtains the run via
`gh api repos/IngvarConsulting/unica-marketplace/actions/runs/{runId}`, validates
manual event, successful conclusion, workflow identity, exact head commit,
ancestor relationship, catalog version, and manifest/profile digests.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_legacy_barrier tests.test_verify_marketplace -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/legacy_barrier.py tests .github/workflows
git commit -m "ci: require a verified legacy barrier before 1.0"
```

### Task 6: Documentation, Timeouts, and Complete Verification

**Files:**
- Modify: `MIGRATION.md`
- Modify: `.github/workflows/legacy-migration-regression.yml`
- Modify: `.github/workflows/legacy-migration-case.yml`
- Modify: `.github/workflows/verify.yml`
- Modify: `tests/test_verify_marketplace.py`

**Interfaces:**
- Documents the operator contract and required check.

- [ ] **Step 1: Add failing documentation assertions**

Require the guide to contain `manual only`, `regression-policy`, `final stable 0.9.x`, and `legacy-migration-barrier.json`, and to omit claims of weekly execution.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_verify_marketplace -v`

Expected: documentation assertions fail.

- [ ] **Step 3: Update docs and operational limits**

Document manual current/barrier modes, automatic promotion scope, receipt lifecycle, and branch-protection requirement. Add 20-minute timeouts to consumer jobs and a manual-workflow concurrency key based on selected ref and profile set.

- [ ] **Step 4: Run the full local verification suite**

Run: `python3 -m unittest discover -s tests -v`

Run: `python3 scripts/verify_marketplace.py`

Run: `actionlint .github/workflows/*.yml .github/actions/setup-locked-codex/action.yml`

Run: `git diff --check`

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add MIGRATION.md .github tests
git commit -m "docs: document marketplace regression policy"
```

### Task 7: Publish PR #9 and Enable the Stable Check

**Files:** none.

**Interfaces:**
- Consumes successful local and hosted checks.
- Produces merged PR #9 and required `regression-policy` status context.

- [ ] **Step 1: Push the branch and refresh PR #9**

Run: `git push origin codex/issue-90-migration-regression`

Run: `gh pr edit 9 --repo IngvarConsulting/unica-marketplace --title "ci: enforce marketplace regression policy"`

- [ ] **Step 2: Wait for every hosted check**

Run: `gh pr checks 9 --repo IngvarConsulting/unica-marketplace --watch --interval 10`

Expected: all non-conditional checks succeed and `regression-policy` succeeds.

- [ ] **Step 3: Mark ready and merge**

Run: `gh pr ready 9 --repo IngvarConsulting/unica-marketplace`

Run: `gh pr merge 9 --repo IngvarConsulting/unica-marketplace --squash --delete-branch=false`

- [ ] **Step 4: Verify main and configure required status**

Wait for the `main` Verify marketplace run to succeed. Configure branch protection for `main` with strict required context `regression-policy` and no unrelated review requirement:

```bash
gh api --method PUT repos/IngvarConsulting/unica-marketplace/branches/main/protection \
  --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["regression-policy"]},"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,"required_conversation_resolution":false,"allow_force_pushes":false,"allow_deletions":false,"block_creations":false,"required_linear_history":false,"lock_branch":false,"allow_fork_syncing":false}
JSON
```

- [ ] **Step 5: Record evidence**

Capture merged commit, main run URL, and branch-protection API response for the release handoff.
