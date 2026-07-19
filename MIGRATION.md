# Migration from a development installation

The transition installers need only Codex and Git. They clone the stable public
marketplace, select the catalog's published semantic-version source release, run native preflight,
and delegate all configuration changes to the same transactional migration
engine on macOS, Linux, and Windows.

POSIX:

```sh
git clone --depth 1 https://github.com/IngvarConsulting/unica.git unica-source
./unica-source/scripts/install-unica.sh
```

Windows PowerShell 5.1 or newer:

```powershell
git clone --depth 1 https://github.com/IngvarConsulting/unica.git unica-source
& .\unica-source\scripts\install-unica.ps1
```

Preflight completes before mutation. The migration records every successful
step, rolls it back in reverse order after a failure, and atomically restores
the exact saved Codex configuration. It prints the retained backup directory.
Rerunning a completed migration is safe.

## Support window

Direct migration from legacy local and `unica-local` installations is supported
through the `0.x` release line. Before upgrading to `1.0`, users of those layouts
must first migrate to the final stable `0.x` release and then use the normal
marketplace update path.

Starting with `1.0`, direct migration from non-marketplace installations will no
longer be supported. Normal installation and updates of an already registered
marketplace remain supported. Removal of the legacy transition code is tracked
in [IngvarConsulting/unica#135](https://github.com/IngvarConsulting/unica/issues/135).

The release gate checks the previous stable marketplace version and the final
stable `0.6` version on macOS, Linux, and Windows. The `0.6` fixture retains the
duplicate canonical/legacy registration from
[IngvarConsulting/unica#90](https://github.com/IngvarConsulting/unica/issues/90)
so nested canonical plugin settings cannot be silently lost again.

## Manual full-history regression

Run the **Full legacy migration regression** workflow from the marketplace
branch or tag that contains the candidate catalog. With no inputs, the workflow
uses the selected workflow ref; the weekly schedule intentionally uses `main`.
An optional `marketplace_ref` override is accepted only when it is a safe Git
ref, and `target_version` can assert the expected source-release version.

Before rebuilding any historical fixture, the workflow resolves the selected
marketplace ref to an exact commit, reads that commit's catalog, requires a
published semantic-version source release (`vX.Y.Z`), and verifies the release
is not a draft and has a publication timestamp. It captures the published
SHA-256 digests of `install-unica.ps1` and `install-unica.sh`, verifies the
downloaded installer on every target OS before execution, and proves the remote
ref still resolves to the selected commit before each migration. It then runs
every supported historical state and the issue #90 duplicate fixture on macOS,
Linux, and Windows. Published source release metadata plus captured SHA-256 digests
is the enforceable contract; GitHub's current releases are not required
to report `isImmutable: true`.
