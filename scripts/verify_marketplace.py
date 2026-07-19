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


def verify_plugin(root: Path) -> str:
    plugin = root / "plugins" / "unica"
    require(plugin.is_dir(), "plugins/unica is missing")
    require(not any(path.is_symlink() for path in plugin.rglob("*")), "plugin contains symlinks")

    descriptor = load_json(plugin / ".codex-plugin" / "plugin.json")
    manifest = load_json(plugin / "runtime-manifest.json")
    version = descriptor.get("version")
    require(isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version) is not None,
            "plugin version is not semantic")
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


def verify_catalog(root: Path, version: str) -> None:
    catalog_path = root / ".agents" / "plugins" / "marketplace.json"
    require(catalog_path.is_file(), "stable marketplace catalog is missing")
    catalog = load_json(catalog_path)
    require(catalog.get("name") == "unica", "marketplace name mismatch")
    plugins = catalog.get("plugins")
    require(isinstance(plugins, list) and len(plugins) == 1, "marketplace must expose one plugin")
    entry = plugins[0]
    require(entry.get("name") == "unica", "catalog plugin name mismatch")
    source = entry.get("source", {})
    require(source.get("source") == "git-subdir", "stable source must use git-subdir")
    require(source.get("url") == MARKETPLACE, "stable source repository mismatch")
    require(source.get("path") == "./plugins/unica", "stable source path mismatch")
    stable_ref = source.get("ref")
    require(isinstance(stable_ref, str) and re.fullmatch(r"v\d+\.\d+\.\d+", stable_ref),
            "stable source ref is not a semantic version tag")
    stable_version = stable_ref.removeprefix("v")
    require(
        tuple(map(int, version.split("."))) >= tuple(map(int, stable_version.split("."))),
        "staged plugin version is older than the stable catalog",
    )
    require(entry.get("policy", {}).get("installation") == "AVAILABLE", "stable policy mismatch")


def verify(root: Path, allow_empty: bool = False) -> str | None:
    plugin = root / "plugins" / "unica"
    if not plugin.exists() and allow_empty:
        require(not (root / ".agents" / "plugins" / "marketplace.json").exists(),
                "catalog cannot exist before the plugin is staged")
        return None
    version = verify_plugin(root)
    catalog = root / ".agents" / "plugins" / "marketplace.json"
    if catalog.exists():
        verify_catalog(root, version)
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()
    version = verify(args.root.resolve(), args.allow_empty)
    print("verified empty pre-release marketplace" if version is None else f"verified Unica marketplace {version}")


if __name__ == "__main__":
    try:
        main()
    except ContractError as error:
        raise SystemExit(str(error)) from error
