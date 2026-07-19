# Unica marketplace

Public Codex marketplace for [Unica](https://github.com/IngvarConsulting/unica),
the 1C:Enterprise development toolkit.

## Install

Prerequisites: a compatible Codex CLI and Git (Git for Windows on Windows).
Node.js, Python, curl, wget, jq, and separate archive utilities are not required.

```sh
codex plugin marketplace add IngvarConsulting/unica-marketplace --ref main
codex plugin add unica@unica
```

Open a new Codex task after installation. The first Unica MCP start downloads
only the runtime for the current operating system, verifies its SHA-256 digest,
and publishes it atomically to the Codex cache. Later starts reuse that cache.

## Update

```sh
codex plugin marketplace upgrade unica
codex plugin remove unica@unica
codex plugin add unica@unica
```

## Delivery contract

Stable catalog entries point at immutable version tags. A release is staged in
`plugins/unica`, tagged only after its checks pass, and promoted in a separate
catalog-only change. See [MIGRATION.md](MIGRATION.md) for transition details.

