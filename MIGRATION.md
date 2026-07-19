# Migration from a development installation

The transition installers need only Codex and Git. They clone the stable public
marketplace, select the catalog's immutable version tag, run native preflight,
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
