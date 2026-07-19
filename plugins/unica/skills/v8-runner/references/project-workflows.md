# Project Workflows

`v8project.yaml` is the project contract. `v8project.local.yaml` is for local secrets and paths and must not redefine shared source topology or `execution_timeout`.

Typical empty workspace order:

1. Create `src/` if there are no source files.
2. Call `unica.runtime.execute` with `operation=config-init`.
3. Call `operation=init` only when the runtime state must be materialized.
4. If the database is the source of truth, call `operation=dump` with `mode=full`.
5. If Git sources are the source of truth, ask before calling `operation=build`.

`build` also prepares configured client MCP tool extensions when the project has `tools.client_mcp.extension`. Use `fullRebuild=true` if that generated state may be stale.

Use `extensions` when only extension properties need synchronization.

Use `tools-download` when the project needs v8-runner-managed YaXUnit, Vanessa, or client MCP tool payloads refreshed.

Use `launch` with `clientMode=mcp` or `clientMode=mcp-va` for client-side MCP workflows; do not hand-assemble platform launch strings.
