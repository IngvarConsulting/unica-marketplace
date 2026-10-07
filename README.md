# Unica marketplace

Public marketplace for [Unica](https://github.com/IngvarConsulting/unica), the
1C:Enterprise development toolkit. One plugin directory serves both Codex and
Claude Code: each host reads its own catalog and manifest and ignores the other.

## Install

Prerequisites: Git (Git for Windows on Windows) and one host — a compatible
Codex CLI with `codex plugin` commands, or Claude Code 2.1.69 or newer. Node.js,
Python, curl, wget, jq, and separate archive utilities are not required.

### Codex

```sh
codex plugin marketplace add IngvarConsulting/unica-marketplace --ref main
codex plugin add unica@unica
```

Open a new Codex task after installation. A running session keeps the skills and
MCP configuration it started with.

### Claude Code

```sh
claude plugin marketplace add IngvarConsulting/unica-marketplace
claude plugin install unica@unica
```

Claude Code adds the catalog without a ref. Run `/reload-plugins` or start a new
session afterwards; skills become available under the plugin namespace, for
example `/unica:meta-validate`. Claude Code 2.1.68 and earlier reject the
catalog's `git-subdir` source type and cannot load it at all.

### Runtime download

The first Unica MCP start downloads only the runtime for the current operating
system and architecture, verifies the archive and every file by SHA-256, and
publishes it atomically to the host cache. Later starts reuse that cache.

| Host | Cache directory |
| --- | --- |
| Codex | `$CODEX_HOME/unica/runtimes` (`~/.codex/unica/runtimes` by default) |
| Claude Code | `${CLAUDE_PLUGIN_DATA}/runtimes`, which survives plugin updates |

## Update

### Codex

```sh
codex plugin marketplace upgrade unica
codex plugin remove unica@unica
codex plugin add unica@unica
```

The supported CLI has no `codex plugin upgrade`, so reinstalling after the
catalog upgrade is a deliberate step. Open a new Codex task afterwards.

### Claude Code

```sh
claude plugin marketplace update unica
claude plugin update unica@unica
```

Then run `/reload-plugins`.

## A branch or an exact version

Add the marketplace by branch to follow a channel, or by tag to stay on one
version:

- **Branch** — `--ref main` for Codex and no suffix for Claude Code serve the
  latest stable release; `--ref next` and `#next` serve the latest release of
  the [candidate channel](#release-candidates). Updating the marketplace brings
  the channel's next release.
- **Tag** — `--ref vX.Y.Z` for Codex and `#vX.Y.Z` for Claude Code install
  exactly X.Y.Z and stay there. A candidate's tag carries the `next` catalog,
  so its plugin is `unica@unica-next`.

```sh
codex plugin marketplace add IngvarConsulting/unica-marketplace --ref v0.13.0-rc.6
codex plugin add unica@unica-next
```

```sh
claude plugin marketplace add IngvarConsulting/unica-marketplace#v0.13.0-rc.6
claude plugin install unica@unica-next
```

Tags `v0.9.1` through `v0.13.0-rc.5` name the staging commit, whose catalogs
still named the previous version, so they install that version instead of
their own: install those versions by branch. From `v0.13.0-rc.6` on, a tag
installs its own version.

A marketplace with the same name (`unica` or `unica-next`) that is already
added by branch must be removed before it is added by tag:

```sh
codex plugin marketplace remove unica-next
claude plugin marketplace remove unica-next
```

## Release candidates

Release candidates (`X.Y.Z-rc.N`) are served only by the `next` branch, as a
separate marketplace named `unica-next`; the `main` catalogs never name a
candidate. The channel holds the newest published version, so its subscribers
receive the full release through the same update that brought the candidate.
Keep only one of `unica@unica` and `unica@unica-next` installed: both start an
MCP server named `unica`. Skip the `remove` or `uninstall` line when the stable
plugin is not installed.

```sh
codex plugin marketplace add IngvarConsulting/unica-marketplace --ref next
codex plugin remove unica@unica
codex plugin add unica@unica-next
```

```sh
claude plugin marketplace add IngvarConsulting/unica-marketplace#next
claude plugin uninstall unica@unica
claude plugin install unica@unica-next
```

Update as in [Update](#update), with `unica-next` for the marketplace and
`unica@unica-next` for the plugin. To return to stable releases, remove
`unica@unica-next` and add `unica@unica` again.

## Uninstall

```sh
codex plugin remove unica@unica
codex plugin marketplace remove unica
```

```sh
claude plugin uninstall unica@unica
claude plugin marketplace remove unica
```

## Delivery contract

Catalog entries point at immutable version tags. The Unica publishing pipeline
stages a release in `plugins/unica` first, without touching a catalog, and
marks that commit with the candidate anchor `candidate-vX.Y.Z`; its install and
upgrade checks resolve the anchor. Only after they pass does a promotion commit
update both catalogs of the channel, `.agents/plugins/marketplace.json` for
Codex and `.claude-plugin/marketplace.json` for Claude Code. The version tag
`vX.Y.Z` is created on that promotion commit and pushed atomically with the
branch, so the catalogs inside a tag always name the tag itself. A stable
release is tagged on `main`, a candidate on `next`. See
[MIGRATION.md](MIGRATION.md) for transition details.

The `next` branch carries the candidate channel. Its catalogs, named
`unica-next`, point at the immutable tag of the newest candidate or stable
release and are never older than the `main` catalogs: a stable release pushes
`main`, its tag and `next` in one atomic push, and leaves `next` alone only
when it already serves a newer candidate. Everything else on `next`
follows `main`: each publication to it brings over the scripts and workflows,
so edit them on `main` only. The consumer install, seed and legacy migration
checks of this repository cover the stable catalog; the publishing pipeline
installs every candidate fresh and upgrades to it with Codex on macOS, Linux
and Windows before `next` moves.
