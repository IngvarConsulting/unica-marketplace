# Troubleshooting

Classify failures before retrying:

- License text means hard stop. Do not repair licensing automatically.
- Authentication failure without credentials allows only `Администратор` with empty password, then `Admin` with empty password, then ask the user.
- Missing platform, runner, tool, VA, or MCP extension is an environment/setup issue; report the exact missing component.
- Stale generated state after branch switch or rebase should use `build` with `fullRebuild=true`.
- Unexpected source changes after dump should be reviewed as a Git diff before continuing.

Do not bypass typed MCP arguments with raw shell flags. If the needed v8-runner flag is missing from `unica.runtime.execute`, treat that as a Unica MCP contract gap.
