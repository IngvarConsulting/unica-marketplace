#!/usr/bin/env python3
"""Validate and materialize the marketplace regression policy contracts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence


TARGETS = {"darwin-arm64", "linux-x64", "win-x64"}
PROFILE_SETS = {"current", "barrier"}
RUNNABLE_CLASSIFICATIONS = {"supported", "transition"}
CLASSIFICATIONS = RUNNABLE_CLASSIFICATIONS | {"excluded"}
SOURCE_KINDS = {"version-bundle", "platform-archive", "source-tag", "marketplace-promotion"}
LAYOUTS = {"legacy-alias", "legacy-canonical", "issue-90-duplicate", "marketplace-canonical"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SEMVER = re.compile(r"(?:v)?(\d+)\.(\d+)\.(\d+)\Z")


class ContractError(ValueError):
    """A regression contract is malformed or ambiguous."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read valid JSON object from {path}: {error}") from error
    _require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def _validate_asset(asset: Any, context: str) -> None:
    _require(isinstance(asset, dict), f"{context} must be an object")
    _require(isinstance(asset.get("name"), str) and bool(asset["name"]), f"{context}.name is required")
    _require(isinstance(asset.get("sha256"), str) and bool(SHA256.fullmatch(asset["sha256"])), f"{context}.sha256 must be lowercase SHA-256")


def load_codex_lock(path: Path) -> dict[str, Any]:
    lock = _load_object(Path(path))
    _require(lock.get("schemaVersion") == 1, "unsupported Codex lock schemaVersion")
    profiles = lock.get("profiles")
    _require(isinstance(profiles, dict), "Codex lock profiles must be an object")
    _require(set(profiles) == {"current", "historical-0.144.1"}, "Codex lock must contain exactly the policy profiles")
    for profile_name, profile in profiles.items():
        _require(isinstance(profile, dict), f"Codex profile {profile_name} must be an object")
        _require(isinstance(profile.get("release"), str) and profile["release"].startswith("rust-v"), f"Codex profile {profile_name} has no release")
        targets = profile.get("targets")
        _require(isinstance(targets, dict) and set(targets) == TARGETS, f"Codex profile {profile_name} must lock all targets")
        for target_name, target in targets.items():
            _require(isinstance(target, dict), f"Codex target {profile_name}/{target_name} must be an object")
            for key in ("asset", "executable"):
                _require(isinstance(target.get(key), str) and bool(target[key]), f"Codex target {profile_name}/{target_name}.{key} is required")
            _require(isinstance(target.get("sha256"), str) and bool(SHA256.fullmatch(target["sha256"])), f"Codex target {profile_name}/{target_name}.sha256 must be lowercase SHA-256")
    return lock


def _validate_release(entry: Any, context: str, *, fixture: bool) -> None:
    _require(isinstance(entry, dict), f"{context} must be an object")
    for key in ("label", "version", "sourceKind", "sourceRef", "sourceCommit"):
        _require(isinstance(entry.get(key), str) and bool(entry[key]), f"{context}.{key} is required")
    _require(bool(SEMVER.fullmatch(entry["version"])), f"{context}.version must be x.y.z")
    _require(entry["sourceKind"] in SOURCE_KINDS, f"{context}.sourceKind is unsupported")
    _require(bool(COMMIT.fullmatch(entry["sourceCommit"])), f"{context}.sourceCommit must be a lowercase full commit")

    if fixture:
        _require("classification" not in entry, f"{context} must not be a release classification")
        _require(entry.get("layout") in LAYOUTS, f"{context}.layout is unsupported")
    else:
        classification = entry.get("classification")
        _require(classification in CLASSIFICATIONS, f"{context}.classification is unsupported")
        if classification == "excluded":
            _require(isinstance(entry.get("reason"), str) and bool(entry["reason"].strip()), f"{context}.reason is required when excluded")
        else:
            _require(entry.get("layout") in LAYOUTS, f"{context}.layout is unsupported")

    if entry["sourceKind"] in {"version-bundle", "platform-archive"}:
        assets = entry.get("assets")
        _require(isinstance(assets, dict) and set(assets) == TARGETS, f"{context}.assets must lock all targets")
        for target_name, asset in assets.items():
            _validate_asset(asset, f"{context}.assets.{target_name}")
    else:
        _require("assets" not in entry, f"{context}.assets are only valid for release archives")


def load_release_inventory(path: Path) -> dict[str, Any]:
    inventory = _load_object(Path(path))
    _require(inventory.get("schemaVersion") == 1, "unsupported release inventory schemaVersion")
    releases = inventory.get("releases")
    fixtures = inventory.get("fixtures")
    _require(isinstance(releases, list) and bool(releases), "release inventory must contain releases")
    _require(isinstance(fixtures, list), "release inventory fixtures must be an array")
    for index, entry in enumerate(releases):
        _validate_release(entry, f"releases[{index}]", fixture=False)
    for index, entry in enumerate(fixtures):
        _validate_release(entry, f"fixtures[{index}]", fixture=True)
    versions = [entry["version"] for entry in releases]
    labels = [entry["label"] for entry in releases] + [entry["label"] for entry in fixtures]
    _require(len(versions) == len(set(versions)), "release inventory versions must be unique")
    _require(len(labels) == len(set(labels)), "release and fixture labels must be unique")
    return inventory


def _case_for(entry: dict[str, Any], codex_profile: str) -> dict[str, Any]:
    case = {
        "label": entry["label"],
        "version": entry["version"],
        "release": entry["sourceRef"],
        "kind": entry["sourceKind"],
        "sourceCommit": entry["sourceCommit"],
        "layout": entry["layout"],
        "codexProfile": codex_profile,
    }
    if "assets" in entry:
        case["assets"] = entry["assets"]
    return case


def build_manual_cases(inventory: dict[str, Any], profile_set: str) -> list[dict[str, Any]]:
    if profile_set not in PROFILE_SETS:
        raise ValueError(f"unsupported profile set: {profile_set}")
    cases = [
        _case_for(entry, "current")
        for entry in inventory.get("releases", [])
        if entry.get("classification") in RUNNABLE_CLASSIFICATIONS
    ]
    cases.extend(_case_for(entry, "current") for entry in inventory.get("fixtures", []))
    if profile_set == "barrier":
        cases.extend(
            _case_for(entry, "historical-0.144.1")
            for entry in inventory.get("releases", [])
            if entry.get("version") == "0.3.11"
        )
        cases.extend(
            _case_for(entry, "historical-0.144.1")
            for entry in inventory.get("fixtures", [])
        )
    return cases


def _version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"invalid release version: {value}")
    return tuple(int(part) for part in match.groups())


def requires_legacy_barrier(previous_version: str, target_version: str) -> bool:
    previous = _version(previous_version)
    target = _version(target_version)
    return previous[0:2] == (0, 9) and target[0] == 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    matrix = commands.add_parser("matrix", help="materialize the manual regression matrix")
    matrix.add_argument("--inventory", type=Path, required=True)
    matrix.add_argument("--profile-set", choices=sorted(PROFILE_SETS), required=True)
    matrix.add_argument("--github-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "matrix":
        inventory = load_release_inventory(args.inventory)
        matrix = build_manual_cases(inventory, args.profile_set)
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write("source_matrix=")
            output.write(json.dumps(matrix, separators=(",", ":")))
            output.write("\n")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
