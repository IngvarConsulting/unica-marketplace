#!/usr/bin/env python3
"""Verify the immutable thin-plugin marketplace contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TARGETS = {"darwin-arm64", "linux-x64", "win-x64"}
BOOTSTRAPS = {
    "darwin-arm64": "unica-bootstrap",
    "linux-x64": "unica-bootstrap",
    "win-x64": "unica-bootstrap.exe",
}
REPOSITORY = "https://github.com/IngvarConsulting/unica"
MARKETPLACE = "https://github.com/IngvarConsulting/unica-marketplace.git"
# main serves the stable catalog; next serves release candidates and every
# stable release after them, under its own marketplace name.
CATALOG_NAMES = {"stable": "unica", "next": "unica-next"}
RELEASE = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
CANDIDATE = RELEASE + r"-rc\.(0|[1-9]\d*)"


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"expected JSON object in {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def is_channel_version(version: object, channel: str) -> bool:
    """A stable channel serves releases only; next also serves `-rc.N` candidates."""
    if not isinstance(version, str):
        return False
    if re.fullmatch(RELEASE, version):
        return True
    return channel == "next" and re.fullmatch(CANDIDATE, version) is not None


def version_key(version: str) -> tuple[int, int, int, int, int]:
    """SemVer order for releases and candidates: a release follows its candidates."""
    match = re.fullmatch(RELEASE + r"(?:-rc\.(0|[1-9]\d*))?", version)
    if match is None:
        raise ContractError(f"not a release or candidate version: {version}")
    major, minor, patch, candidate = match.groups()
    if candidate is None:
        return (int(major), int(minor), int(patch), 1, 0)
    return (int(major), int(minor), int(patch), 0, int(candidate))


def verify_plugin(root: Path, channel: str = "stable") -> str:
    plugin = root / "plugins" / "unica"
    require(plugin.is_dir(), "plugins/unica is missing")
    require(not any(path.is_symlink() for path in plugin.rglob("*")), "plugin contains symlinks")

    descriptor = load_json(plugin / ".codex-plugin" / "plugin.json")
    manifest = load_json(plugin / "runtime-manifest.json")
    version = descriptor.get("version")
    require(is_channel_version(version, channel), "plugin version is not semantic")
    require(manifest.get("schemaVersion") == 1, "runtime manifest schema mismatch")
    require(manifest.get("pluginVersion") == version, "plugin/runtime version mismatch")
    require(manifest.get("development") is False, "development runtime manifest is forbidden")
    require(manifest.get("source", {}).get("repository") == REPOSITORY, "source repository mismatch")
    require(manifest.get("release", {}).get("repository") == REPOSITORY, "release repository mismatch")
    require(manifest.get("release", {}).get("tag") == f"v{version}", "release tag is not version-pinned")
    require(set(manifest.get("targets", {})) == TARGETS, "runtime target matrix mismatch")

    for target, executable in BOOTSTRAPS.items():
        path = plugin / "bootstrap" / "bin" / target / executable
        require(path.is_file(), f"missing native bootstrap: {path.relative_to(root)}")
    require((plugin / "bootstrap" / "launch.sh").is_file(), "portable Git launcher is missing")
    require(not (plugin / "bin").exists(), "thin plugin contains the full runtime bin directory")

    mcp = load_json(plugin / ".mcp.json").get("mcpServers", {}).get("unica", {})
    require(mcp.get("command") == "git", "MCP entrypoint must be Git")
    args = mcp.get("args", [])
    require(isinstance(args, list) and len(args) >= 3, "Git MCP entrypoint arguments are incomplete")
    require("alias.unica-bootstrap=" in args[1], "command-scoped Git alias is missing")
    require(args[2] == "unica-bootstrap", "Git alias invocation mismatch")

    for path in plugin.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".toml", ".sh", ".ps1"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            require("unica-local" not in text, f"legacy consumer name in {path.relative_to(root)}")
    return version


def verify_source(source: object, channel: str) -> str:
    require(isinstance(source, dict), f"{channel} source is missing")
    require(source.get("source") == "git-subdir", f"{channel} source must use git-subdir")
    require(source.get("url") == MARKETPLACE, f"{channel} source repository mismatch")
    # Bare form only: a "./" prefix breaks `git sparse-checkout set --cone`
    # on git <= 2.34, where the argument lands as a literal non-matching pattern.
    require(source.get("path") == "plugins/unica", f"{channel} source path mismatch")
    ref = source.get("ref")
    require(isinstance(ref, str) and ref.startswith("v") and is_channel_version(ref[1:], channel),
            f"{channel} source ref is not a semantic version tag")
    return ref


def verify_catalog(root: Path, version: str, channel: str = "stable") -> None:
    catalog_path = root / ".agents" / "plugins" / "marketplace.json"
    require(catalog_path.is_file(), f"{channel} marketplace catalog is missing")
    catalog = load_json(catalog_path)
    require(catalog.get("name") == CATALOG_NAMES[channel], "marketplace name mismatch")
    plugins = catalog.get("plugins")
    require(isinstance(plugins, list) and len(plugins) == 1, "marketplace must expose one plugin")
    entry = plugins[0]
    require(entry.get("name") == "unica", "catalog plugin name mismatch")
    served_ref = verify_source(entry.get("source"), channel)
    require(
        version_key(version) >= version_key(served_ref.removeprefix("v")),
        f"staged plugin version is older than the {channel} catalog",
    )
    require(entry.get("policy", {}).get("installation") == "AVAILABLE", f"{channel} policy mismatch")

    # Claude Code reads its own catalog, which must serve the same release: a
    # prerelease reaching either host through main is the same failure.
    claude_path = root / ".claude-plugin" / "marketplace.json"
    require(claude_path.is_file(), f"{channel} Claude catalog is missing")
    claude = load_json(claude_path)
    require(claude.get("name") == CATALOG_NAMES[channel], "Claude marketplace name mismatch")
    claude_plugins = claude.get("plugins")
    require(isinstance(claude_plugins, list) and len(claude_plugins) == 1,
            "Claude marketplace must expose one plugin")
    claude_entry = claude_plugins[0]
    require(claude_entry.get("name") == "unica", "Claude catalog plugin name mismatch")
    require(verify_source(claude_entry.get("source"), channel) == served_ref,
            "host catalogs serve different releases")
    # Claude Code detects an update by this string, so it names the served release.
    require(claude_entry.get("version") == served_ref.removeprefix("v"),
            "Claude catalog version does not name the served release")


def verify(root: Path, allow_empty: bool = False, channel: str = "stable") -> str | None:
    plugin = root / "plugins" / "unica"
    if not plugin.exists() and allow_empty:
        require(not (root / ".agents" / "plugins" / "marketplace.json").exists(),
                "catalog cannot exist before the plugin is staged")
        return None
    version = verify_plugin(root, channel)
    catalog = root / ".agents" / "plugins" / "marketplace.json"
    if catalog.exists():
        verify_catalog(root, version, channel)
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--channel", choices=sorted(CATALOG_NAMES), default="stable")
    args = parser.parse_args()
    version = verify(args.root.resolve(), args.allow_empty, args.channel)
    print("verified empty pre-release marketplace" if version is None else f"verified Unica marketplace {version}")


if __name__ == "__main__":
    try:
        main()
    except ContractError as error:
        raise SystemExit(str(error)) from error
