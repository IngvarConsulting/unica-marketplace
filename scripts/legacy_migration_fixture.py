#!/usr/bin/env python3
"""Rebuild an isolated historical Codex installation from published Unica bits."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, List


LAYOUTS = {
    "legacy-alias",
    "legacy-canonical",
    "issue-90-duplicate",
    "marketplace-canonical",
}
MARKETPLACE_SOURCE = "https://github.com/IngvarConsulting/unica-marketplace.git"


class FixtureError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def _safe_archive_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _extract_archive(archive: Path, destination: Path) -> None:
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as package:
            members = package.getmembers()
            for member in members:
                _require(_safe_archive_path(member.name), f"unsafe archive path: {member.name}")
                _require(
                    not member.issym() and not member.islnk(),
                    f"archive links are forbidden: {member.name}",
                )
            package.extractall(destination, members=members)
        return
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                _require(_safe_archive_path(member.filename), f"unsafe archive path: {member.filename}")
                file_type = (member.external_attr >> 16) & 0o170000
                _require(
                    file_type != stat.S_IFLNK,
                    f"archive links are forbidden: {member.filename}",
                )
            package.extractall(destination)
        return
    raise FixtureError(f"unsupported release archive: {archive}")


def _load_json(path: Path) -> Dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureError(f"cannot read valid JSON from {path}: {error}") from error
    _require(isinstance(value, dict), f"expected JSON object in {path}")
    return value


def _find_plugin_root(extracted: Path, version: str) -> Path:
    descriptors = list(extracted.glob("**/plugins/unica/.codex-plugin/plugin.json"))
    _require(len(descriptors) == 1, "release archive must contain exactly one Unica plugin")
    descriptor = _load_json(descriptors[0])
    _require(descriptor.get("name") == "unica", "release archive plugin name is not unica")
    _require(
        descriptor.get("version") == version,
        f"expected plugin version {version}, found {descriptor.get('version')}",
    )
    return descriptors[0].parents[1]


def _validate_legacy_marketplace(plugin_root: Path) -> Path:
    marketplace_root = plugin_root.parents[1]
    manifest_path = marketplace_root / ".agents" / "plugins" / "marketplace.json"
    manifest = _load_json(manifest_path)
    _require(manifest.get("name") == "unica", "legacy marketplace name is not unica")
    plugins = manifest.get("plugins")
    _require(isinstance(plugins, list) and len(plugins) == 1, "legacy marketplace must expose one plugin")
    entry = plugins[0]
    _require(isinstance(entry, dict) and entry.get("name") == "unica", "legacy plugin entry is invalid")
    source = entry.get("source")
    _require(
        isinstance(source, dict)
        and source.get("source") == "local"
        and source.get("path") in {"./plugins/unica", "plugins/unica"},
        "legacy marketplace source is not the packaged Unica plugin",
    )
    return marketplace_root


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _local_marketplace_config(source: Path) -> List[str]:
    return [
        "[marketplaces.unica]",
        'last_updated = "1970-01-01T00:00:00Z"',
        'source_type = "local"',
        f"source = {_toml_string(str(source.resolve()))}",
        "",
    ]


def _git_marketplace_config() -> List[str]:
    return [
        "[marketplaces.unica]",
        'last_updated = "1970-01-01T00:00:00Z"',
        'source_type = "git"',
        f"source = {_toml_string(MARKETPLACE_SOURCE)}",
        'ref = "main"',
        "",
    ]


def _plugin_config(plugin_id: str, *, marker: bool = False) -> List[str]:
    lines = [f'[plugins."{plugin_id}"]', "enabled = true", ""]
    if marker:
        lines.extend(
            [
                f'[plugins."{plugin_id}".settings]',
                'issue_90_marker = "preserve-me"',
                "",
            ]
        )
    return lines


def _copy_plugin(plugin_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(plugin_root, destination)


def prepare_fixture(
    archive: Path,
    codex_home: Path,
    version: str,
    layout: str,
) -> Dict[str, object]:
    archive = archive.resolve()
    codex_home = codex_home.resolve()
    _require(archive.is_file(), f"release archive is missing: {archive}")
    _require(layout in LAYOUTS, f"unsupported fixture layout: {layout}")
    _require(
        not codex_home.exists() or not any(codex_home.iterdir()),
        f"Codex home must be empty: {codex_home}",
    )
    codex_home.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="unica-legacy-extract-") as directory:
        extracted = Path(directory)
        _extract_archive(archive, extracted)
        plugin_root = _find_plugin_root(extracted, version)
        config: List[str]
        plugin_ids: List[str]

        if layout == "marketplace-canonical":
            config = _git_marketplace_config()
            plugin_ids = ["unica@unica"]
            _copy_plugin(
                plugin_root,
                codex_home / "plugins" / "cache" / "unica" / "unica" / version,
            )
            config.extend(_plugin_config("unica@unica"))
        else:
            marketplace_root = _validate_legacy_marketplace(plugin_root)
            installed_marketplace = codex_home / "marketplaces" / "unica-local"
            installed_marketplace.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(marketplace_root, installed_marketplace)
            installed_plugin = installed_marketplace / "plugins" / "unica"
            config = _local_marketplace_config(installed_marketplace)

            if layout == "legacy-alias":
                plugin_ids = ["unica@unica-local"]
                _copy_plugin(
                    installed_plugin,
                    codex_home
                    / "plugins"
                    / "cache"
                    / "unica-local"
                    / "unica"
                    / version,
                )
                config.extend(_plugin_config("unica@unica-local"))
            elif layout == "legacy-canonical":
                plugin_ids = ["unica@unica"]
                _copy_plugin(
                    installed_plugin,
                    codex_home / "plugins" / "cache" / "unica" / "unica" / version,
                )
                config.extend(_plugin_config("unica@unica"))
            else:
                plugin_ids = ["unica@unica", "unica@unica-local"]
                for marketplace_name in ("unica", "unica-local"):
                    _copy_plugin(
                        installed_plugin,
                        codex_home
                        / "plugins"
                        / "cache"
                        / marketplace_name
                        / "unica"
                        / version,
                    )
                config.extend(_plugin_config("unica@unica", marker=True))
                config.extend(_plugin_config("unica@unica-local"))

    config_path = codex_home / "config.toml"
    config_path.write_text("\n".join(config), encoding="utf-8")
    return {
        "version": version,
        "layout": layout,
        "pluginIds": plugin_ids,
        "codexHome": str(codex_home),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--layout", choices=sorted(LAYOUTS), required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare_fixture(args.archive, args.codex_home, args.version, args.layout),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except FixtureError as error:
        raise SystemExit(str(error)) from error
