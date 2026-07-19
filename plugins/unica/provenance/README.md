# Skill Upstream Provenance

This directory is maintainer metadata for tracking where Unica skill behavior,
guidance, and runtime contracts came from.

It is intentionally packaged with the plugin, but it is not prompt-visible
workflow guidance. Do not move these donor URLs into `skills/` or `references/`.

## Files

- `skill-upstreams.json` maps Unica skills and contracts to upstream repositories.
- `reviews/*.json` stores maintainer review notes for donor changes that happened
  after the last local Unica skill adaptation.
- `../../third-party/tools.lock.json` remains the single source of bundled binary
  versions, tags, commits, licenses, and assets.

Every packaged skill directory under `../skills/` must have at least one
matching `entries[].skill` value in the index. A skill may appear more than
once when different donors contributed different parts of its behavior; for
example, one source can track operation parity while another tracks guidance.

An entry may set its own `baselineCommit` after that specific skill is reviewed
or adapted. This lets maintainers close drift for one skill without moving the
whole donor repository baseline. Valid entry decisions are `ported`,
`ignored-with-reason`, `blocked-by-product-contract`, and `needs-tool-update`.

## Workflow

1. Run offline validation. This checks JSON shape, path coverage, skill coverage,
   and `toolLockRef` consistency:

   ```sh
   python3.12 scripts/ci/check-skill-upstreams.py --validate-only
   ```

2. Check donor drift from the real adaptation baseline:

   ```sh
   python3.12 scripts/ci/check-skill-upstreams.py --check
   ```

   `baselineCommit` must point to the donor commit that matches the last local
   skill adaptation, not to the current donor head. For bundled tools, the
   baseline comes from `third-party/tools.lock.json`.

3. Generate or refresh a review bundle when you need a JSON artifact:

   ```sh
   python3.12 scripts/ci/check-skill-upstreams.py --prepare-upstream-review --format json
   ```

   Use `--format json` when you need the per-skill `entries[]` report with
   `upstreamDrift` flags. The report intentionally does not store file hashes;
   the useful data is the donor range, changed watched paths, affected skills,
   and maintainer decision.

4. Review the upstream diff and decide whether to port changes.
5. Adapt any accepted changes to Unica's public MCP contract (`unica.*` tools).
6. Update the entry `baselineCommit` for a reviewed skill, update the upstream
   `baselineCommit` only when the whole donor is caught up, or update
   `third-party/tools.lock.json` for bundled tool donors.

Product update backlogs live in the same `reviews/` directory. They are package
metadata, not prompt-visible skill routing guidance.

After updating bundled tools, run the contract smoke against the packaged or
locally installed native binaries:

```sh
python3.12 scripts/ci/check-tool-contracts.py --target darwin-arm64 --tools-dir plugins/unica/bin/darwin-arm64
```

Pass `--rlm-db <path/to/bsl_index.db>` when validating an actual
`rlm-bsl-index` database; the schema check covers the tables and columns used
by Unica's `WorkspaceIndexService`.

For `runtime-tool-contract` entries, provenance tracks the skill and MCP
contract derived from a runtime tool repository. The binary version is not
duplicated here; it is read from `third-party/tools.lock.json` through
`toolLockRef`.
