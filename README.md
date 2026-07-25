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

Stable catalog entries point at immutable version tags. A release is staged in
`plugins/unica` first. A separate promotion commit updates both stable catalogs,
`.agents/plugins/marketplace.json` for Codex and `.claude-plugin/marketplace.json`
for Claude Code; the signed version tag is created on that exact commit, and the
promotion is merged only after its checks pass. See [MIGRATION.md](MIGRATION.md)
for transition details.
