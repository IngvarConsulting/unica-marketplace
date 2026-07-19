# File And Artifact Workflows

Use `dump` to bring database changes into Git-visible files. Check the worktree before dump and review the diff after dump.

Use `dump` with:

- `mode=incremental` for ordinary database-to-source synchronization.
- `mode=full` for first workspace fill or explicit full export.
- `mode=partial` plus `object` or `objects` when the backend supports scoped export.
- `sourceSet` or `extension` for scoped export.

Use `convert` for Designer/EDT source conversion. It is repository-aware and does not require an infobase.

Use `make` for `.cf`, `.cfe`, `.epf`, or `.erf` artifacts. Provide `output`; add `sourceSet` or `extension` when the target is not the default source. For external processors/reports, `output` is a publish directory, not a single `.epf`/`.erf` filename.

Use `load` for applying `.cf` or `.cfe` artifacts. Supported modes are `load` and `merge`; `merge` requires `settings`, and `update` is not a supported load mode. v8-runner rejects `.epf` and `.erf` for `load`; external processors/reports are handled through external source-sets with `build`, `dump`, and `make`.
