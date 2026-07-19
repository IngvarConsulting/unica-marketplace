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

