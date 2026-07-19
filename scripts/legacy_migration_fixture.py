#!/usr/bin/env python3
"""Rebuild an isolated historical Codex installation from published Unica bits."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, List


LAYOUTS = {
    "legacy-alias",
    "legacy-canonical",
    "issue-90-duplicate",
    "marketplace-canonical",
}
MARKETPLACE_SOURCE = "https://github.com/IngvarConsulting/unica-marketplace.git"
ROLLBACK_ROOTS = (
    "config.toml",
    "marketplaces/unica",
    "marketplaces/unica-local",
    ".tmp/marketplaces/unica",
    "plugins/cache/unica",
    "plugins/cache/unica-local",
)


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


def _validate_marketplace_snapshot(plugin_root: Path) -> Path:
    marketplace_root = plugin_root.parents[1]
    manifest = _load_json(
        marketplace_root / ".agents" / "plugins" / "marketplace.json"
    )
    _require(manifest.get("name") == "unica", "marketplace snapshot name is not unica")
    plugins = manifest.get("plugins")
    _require(
        isinstance(plugins, list)
        and len(plugins) == 1
        and isinstance(plugins[0], dict)
        and plugins[0].get("name") == "unica",
        "marketplace snapshot must expose one Unica plugin",
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
    updated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return [
        "[marketplaces.unica]",
        f"last_updated = {_toml_string(updated)}",
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


def _snapshot_entry(codex_home: Path, path: Path) -> Dict[str, object]:
    relative = path.relative_to(codex_home).as_posix()
    metadata = path.lstat()
    entry: Dict[str, object] = {
        "path": relative,
        "mode": stat.S_IMODE(metadata.st_mode),
    }
    if path.is_symlink():
        raise FixtureError(f"rollback state contains a forbidden link: {relative}")
    if path.is_dir():
        entry["kind"] = "directory"
    elif path.is_file():
        contents = path.read_bytes()
        entry.update(
            {
                "kind": "file",
                "size": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
            }
        )
    else:
        raise FixtureError(f"rollback state contains an unsupported entry: {relative}")
    return entry


def snapshot_state(codex_home: Path) -> Dict[str, object]:
    """Capture exact rollback-relevant Codex state, including file modes."""

    codex_home = codex_home.resolve()
    _require(codex_home.is_dir(), f"Codex home is missing: {codex_home}")
    entries: List[Dict[str, object]] = []
    for relative in ROLLBACK_ROOTS:
        root = codex_home / relative
        if not root.exists() and not root.is_symlink():
            continue
        entries.append(_snapshot_entry(codex_home, root))
        if root.is_dir():
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                entries.append(_snapshot_entry(codex_home, path))
    return {"schemaVersion": 1, "entries": entries}


def compare_snapshot(codex_home: Path, expected: Dict[str, object]) -> None:
    """Fail when rollback-relevant state differs from a captured snapshot."""

    _require(expected.get("schemaVersion") == 1, "unsupported rollback snapshot schema")
    expected_entries = expected.get("entries")
    _require(isinstance(expected_entries, list), "rollback snapshot entries must be an array")
    actual = snapshot_state(codex_home)
    if actual != expected:
        expected_by_path = {
            entry.get("path"): entry for entry in expected_entries if isinstance(entry, dict)
        }
        actual_by_path = {
            entry.get("path"): entry
            for entry in actual["entries"]
            if isinstance(entry, dict)
        }
        changed = sorted(
            path
            for path in set(expected_by_path) | set(actual_by_path)
            if expected_by_path.get(path) != actual_by_path.get(path)
        )
        raise FixtureError(
            "rollback state differs from the snapshot: " + ", ".join(str(path) for path in changed)
        )


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
            marketplace_root = _validate_marketplace_snapshot(plugin_root)
            config = _git_marketplace_config()
            plugin_ids = ["unica@unica"]
            snapshot = codex_home / ".tmp" / "marketplaces" / "unica"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(marketplace_root, snapshot)
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
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--version")
    parser.add_argument("--layout", choices=sorted(LAYOUTS))
    snapshot = parser.add_mutually_exclusive_group()
    snapshot.add_argument("--snapshot-output", type=Path)
    snapshot.add_argument("--compare-snapshot", type=Path)
    args = parser.parse_args()
    if args.snapshot_output:
        args.snapshot_output.write_text(
            json.dumps(snapshot_state(args.codex_home), indent=2) + "\n",
            encoding="utf-8",
        )
        return
    if args.compare_snapshot:
        compare_snapshot(args.codex_home, _load_json(args.compare_snapshot))
        return
    if not args.archive or not args.version or not args.layout:
        parser.error("--archive, --version, and --layout are required to prepare a fixture")
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
