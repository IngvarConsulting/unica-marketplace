# Testing

Test operations build first, so avoid a separate build unless the user asked for build-only diagnostics.

Use `operation=test`, `testRunner=yaxunit`, `testScope=all` for full YaXUnit.
Add `fullOutput=true` when you need the runner `--full` output verbosity.
This is not a source build full rebuild.

Use `operation=test`, `testRunner=yaxunit`, `testScope=module`, and `module=<name>` for narrow module-level tests.

Use `operation=test`, `testRunner=va` for the configured Vanessa Automation profile. Optional VA narrowing arguments are `features`, `filterTags`, `ignoreTags`, and `scenarioFilters`. Do not invent feature paths without inspecting project test configuration.

Use `operation=launch`, `clientMode=mcp-va` for interactive Vanessa Automation scenario authoring and debugging through client MCP.

Syntax validation uses `operation=syntax` with `mode=designer-modules`, `mode=designer-config`, or `mode=edt`. Designer syntax accepts client/server flags such as `server`, `thinClient`, `webClient`, `mobileClient`, `extension`, and `allExtensions`; EDT syntax accepts `projects`.

Preserve failed test artifacts and report their path when the runner prints one.
