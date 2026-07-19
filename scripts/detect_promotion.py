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
MARKETPLACE = "https://github.com/IngvarConsulting/unica-marketplace.git"
SEMANTIC_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


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
    if descriptor is None:
        return ""
    version = descriptor.get("version")
    if not isinstance(version, str) or SEMANTIC_VERSION.fullmatch(version) is None:
        raise RuntimeError(f"plugin version in {PLUGIN_PATH} at {commit} must be semantic")
    return version


def catalog_ref_at(root: Path, commit: str) -> str:
    catalog = read_json_at(root, commit, CATALOG_PATH)
    if catalog is None:
        return ""
    if catalog.get("name") != "unica":
        raise RuntimeError(f"catalog at {commit} must be named unica")
    plugins = catalog.get("plugins")
    if (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
        or plugins[0].get("name") != "unica"
    ):
        raise RuntimeError(f"catalog at {commit} must contain exactly one Unica plugin")
    source = plugins[0].get("source")
    if (
        not isinstance(source, dict)
        or source.get("source") != "git-subdir"
        or source.get("url") != MARKETPLACE
        or source.get("path") != "./plugins/unica"
    ):
        raise RuntimeError(f"catalog source at {commit} must use the expected Unica git-subdir")
    ref = source.get("ref")
    if (
        not isinstance(ref, str)
        or re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", ref) is None
    ):
        raise RuntimeError(f"catalog source ref at {commit} must be a semantic version tag")
    return ref


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
    has_plugin = bool(plugin_version)
    catalog_promoted = bool(catalog_ref) and catalog_ref != previous_catalog_ref
    catalog_matches_plugin = has_plugin and plugin_version == catalog_version
    promotion_required = (
        catalog_promoted
        and catalog_matches_plugin
        and bool(previous_catalog_version)
        and previous_catalog_version != catalog_version
    )
    seed_required = (
        event_name == "push"
        and event_ref == "refs/heads/main"
        and has_plugin
        and bool(catalog_version)
        and not catalog_matches_plugin
    )
    return {
        "has_plugin": str(has_plugin).lower(),
        "catalog_promoted": str(catalog_promoted).lower(),
        "catalog_matches_plugin": str(catalog_matches_plugin).lower(),
        "promotion_required": str(promotion_required).lower(),
        "seed_required": str(seed_required).lower(),
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
