# Migration through the v0.7.6 bridge

Unica `v0.7.6` is the immutable migration bridge for old local, duplicated,
and `unica-local` installations. Later releases do not own direct migration
from those layouts.

Use the installer published by the source `v0.7.6` release, not a mutable copy
from a repository branch.

POSIX:

```sh
curl -fLO https://github.com/IngvarConsulting/unica/releases/download/v0.7.6/install-unica.sh
sh install-unica.sh
```

Windows PowerShell 5.1 or newer:

```powershell
Invoke-WebRequest https://github.com/IngvarConsulting/unica/releases/download/v0.7.6/install-unica.ps1 -OutFile install-unica.ps1
& .\install-unica.ps1
```

The published script itself needs only Codex CLI and Git. It selects the
catalog's published semantic-version source release, runs native preflight, and
delegates all mutation to the transactional migration engine. Preflight
finishes before any change. A failed migration rolls successful steps back in
reverse order and restores the exact Codex configuration and owned paths. The
retained backup directory is printed for diagnostics.

## Supported transition boundary

| Starting state | Required path |
| --- | --- |
| Local, duplicated, `unica-local`, or another legacy layout | Run the frozen `v0.7.6` installer above. |
| Canonical marketplace `v0.7.5` | Use the ordinary marketplace update path. |
| Canonical marketplace `v0.7.6` | Use the ordinary marketplace update path to `v0.8.0`. |
| Canonical technical `0.7.x` | Use the ordinary marketplace update path to `v0.8.0`; version alone does not make a legacy layout canonical. |

Starting with `v0.8.0`, direct migration from non-marketplace installations is
not part of the current package. Removal of the legacy implementation is
tracked in
[IngvarConsulting/unica#135](https://github.com/IngvarConsulting/unica/issues/135).

## Automatic promotion policy

The required `regression-policy` check stays intentionally bounded. On macOS,
Linux, and Windows it verifies:

- staged package integrity;
- a fresh installation from the candidate catalog;
- an ordinary canonical update from the immediately previous stable release;
- the exact marketplace ref, commit, source tag, and published installer
  digests used by a promotion.

Issue #90 is not a permanent automatic gate. Its old paths cannot change, so
the fixture belongs to the manual bridge regression.

## Manual full-history regression

Run the **Full legacy migration regression** workflow manually from the
marketplace branch or tag that contains the candidate catalog. The workflow is
`workflow_dispatch` only. It has no scheduled or pull-request trigger.

With no ref override, the workflow uses the selected workflow ref. An optional
`marketplace_ref` is accepted only when it is a safe Git ref, and
`target_version` can assert the expected source release. Select `profile_set`
`current` for the complete matrix on the current locked Codex CLI. Select
`bridge` for the same matrix plus the representative `v0.3.11` and issue #90
states on historical Codex CLI `0.144.1`.

Before rebuilding fixtures, the workflow resolves the selected ref to an exact
commit, reads that commit's catalog, requires a published semantic-version
source release, and uses captured SHA-256 digests of `install-unica.ps1` and
`install-unica.sh`. Every target verifies the downloaded installer before
execution and proves that the remote ref did not move.

Each successful case proves the target version, one canonical `unica@unica`,
legacy cleanup, settings preservation, MCP and prompt visibility, absence of
duplicate registrations, and an idempotent second run. Separate manual jobs on
all three operating systems inject a post-mutation Codex failure and compare the
restored consumer state with its exact preflight snapshot.

There is no later migration receipt or `1.0` barrier. The durable compatibility
artifact is the published and manually verified `v0.7.6` bridge itself.
