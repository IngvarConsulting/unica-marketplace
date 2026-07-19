#!/usr/bin/env python3
"""Resolve exact event-tree versions and semantic catalog promotion state."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


PLUGIN_PATH = "plugins/unica/.codex-plugin/plugin.json"
CATALOG_PATH = ".agents/plugins/marketplace.json"


def require_commit(root: Path, commit: str, label: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise RuntimeError(f"{label} is not a valid commit: {commit}")
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{label} commit is unavailable: {commit}")


def read_json_at(root: Path, commit: str, path: str) -> dict | None:
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{path}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if exists.returncode != 0:
        return None
    content = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if content.returncode != 0:
        raise RuntimeError(f"cannot read {path} at {commit}: {content.stderr.strip()}")
    try:
        value = json.loads(content.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"cannot parse {path} at {commit}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object in {path} at {commit}")
    return value


def plugin_version_at(root: Path, commit: str) -> str:
    descriptor = read_json_at(root, commit, PLUGIN_PATH)
    version = descriptor.get("version") if descriptor is not None else ""
    return version if isinstance(version, str) else ""


def catalog_ref_at(root: Path, commit: str) -> str:
    catalog = read_json_at(root, commit, CATALOG_PATH)
    if catalog is None:
        return ""
    plugins = catalog.get("plugins")
    if not isinstance(plugins, list) or not plugins or not isinstance(plugins[0], dict):
        return ""
    source = plugins[0].get("source")
    if not isinstance(source, dict):
        return ""
    ref = source.get("ref")
    return ref if isinstance(ref, str) else ""


def detect(
    *,
    root: Path,
    event_name: str,
    event_ref: str,
    event_sha: str,
    before_sha: str,
    pr_base_sha: str,
    pr_head_sha: str,
) -> dict[str, str]:
    if event_name == "pull_request":
        event_tree = pr_head_sha
        previous_tree = pr_base_sha
        require_commit(root, event_tree, "pull request head")
        require_commit(root, previous_tree, "pull request base")
    else:
        event_tree = event_sha
        previous_tree = ""
        require_commit(root, event_tree, "event")
        if (
            event_name == "push"
            and event_ref == "refs/heads/main"
            and before_sha
            and set(before_sha) != {"0"}
        ):
            previous_tree = before_sha
            require_commit(root, previous_tree, "push before")

    plugin_version = plugin_version_at(root, event_tree)
    catalog_ref = catalog_ref_at(root, event_tree)
    previous_catalog_ref = catalog_ref_at(root, previous_tree) if previous_tree else ""
    catalog_version = catalog_ref.removeprefix("v")
    previous_catalog_version = previous_catalog_ref.removeprefix("v")
    return {
        "has_plugin": str(bool(plugin_version)).lower(),
        "catalog_promoted": str(bool(catalog_ref) and catalog_ref != previous_catalog_ref).lower(),
        "catalog_matches_plugin": str(bool(plugin_version) and plugin_version == catalog_version).lower(),
        "previous_catalog_version": previous_catalog_version,
        "catalog_version": catalog_version,
        "plugin_version": plugin_version,
    }


def main() -> None:
    outputs = detect(
        root=Path.cwd(),
        event_name=os.environ.get("EVENT_NAME", ""),
        event_ref=os.environ.get("EVENT_REF", ""),
        event_sha=os.environ.get("EVENT_SHA", ""),
        before_sha=os.environ.get("BEFORE_SHA", ""),
        pr_base_sha=os.environ.get("PR_BASE_SHA", ""),
        pr_head_sha=os.environ.get("PR_HEAD_SHA", ""),
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        for key, value in outputs.items():
            output.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
