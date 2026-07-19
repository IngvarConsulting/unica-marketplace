from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "regression_policy.py"
CODEX_LOCK = ROOT / ".github" / "contracts" / "codex-cli-lock.json"
RELEASES = ROOT / ".github" / "contracts" / "legacy-releases.json"


def load_policy():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing regression policy module: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("regression_policy", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load regression policy module: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegressionPolicyTests(unittest.TestCase):
    def test_codex_lock_contains_current_and_historical_profiles(self) -> None:
        policy = load_policy()

        lock = policy.load_codex_lock(CODEX_LOCK)

        self.assertEqual(lock["schemaVersion"], 1)
        self.assertEqual(
            set(lock["profiles"]), {"current", "historical-0.144.1"}
        )
        self.assertEqual(
            lock["profiles"]["current"]["release"], "rust-v0.145.0-alpha.18"
        )
        self.assertEqual(
            lock["profiles"]["historical-0.144.1"]["release"], "rust-v0.144.1"
        )
        for profile in lock["profiles"].values():
            self.assertEqual(
                set(profile["targets"]), {"darwin-arm64", "linux-x64", "win-x64"}
            )
            for target in profile["targets"].values():
                self.assertRegex(target["sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(target["asset"])
                self.assertTrue(target["executable"])

    def test_inventory_classifies_every_published_pre_075_release(self) -> None:
        policy = load_policy()

        inventory = policy.load_release_inventory(RELEASES)

        self.assertEqual(inventory["schemaVersion"], 1)
        expected = {
            "0.3.3",
            "0.3.4",
            "0.3.5",
            "0.3.6",
            "0.3.10",
            "0.3.11",
            "0.3.12",
            "0.4.1",
            "0.4.2",
            "0.4.3",
            "0.4.4",
            "0.5.1",
            "0.6.1",
            "0.7.0",
            "0.7.1",
            "0.7.2",
            "0.7.4",
            "0.7.5",
        }
        self.assertEqual({entry["version"] for entry in inventory["releases"]}, expected)
        by_version = {entry["version"]: entry for entry in inventory["releases"]}
        for version in ("0.3.4", "0.3.5", "0.3.6"):
            self.assertEqual(by_version[version]["sourceKind"], "source-tag")
            self.assertRegex(by_version[version]["sourceCommit"], r"^[0-9a-f]{40}$")
        for version in ("0.7.0", "0.7.1", "0.7.4"):
            self.assertEqual(by_version[version]["classification"], "excluded")
            self.assertTrue(by_version[version]["reason"])

    def test_current_profile_runs_supported_history_and_issue_90_once(self) -> None:
        policy = load_policy()
        inventory = policy.load_release_inventory(RELEASES)

        cases = policy.build_manual_cases(inventory, "current")

        self.assertEqual({case["codexProfile"] for case in cases}, {"current"})
        self.assertEqual(
            [case["label"] for case in cases].count("issue-90-duplicate"), 1
        )
        self.assertNotIn("v0.7.0", {case["label"] for case in cases})
        self.assertNotIn("v0.7.1", {case["label"] for case in cases})
        self.assertNotIn("v0.7.4", {case["label"] for case in cases})

    def test_barrier_profile_does_not_double_the_full_matrix(self) -> None:
        policy = load_policy()
        inventory = policy.load_release_inventory(RELEASES)

        cases = policy.build_manual_cases(inventory, "barrier")

        historical = [
            case["label"]
            for case in cases
            if case["codexProfile"] == "historical-0.144.1"
        ]
        self.assertEqual(historical, ["v0.3.11", "issue-90-duplicate"])

    def test_only_final_zero_nine_to_one_requires_barrier(self) -> None:
        policy = load_policy()

        self.assertTrue(policy.requires_legacy_barrier("0.9.8", "1.0.0"))
        self.assertFalse(policy.requires_legacy_barrier("0.9.7", "0.9.8"))
        self.assertFalse(policy.requires_legacy_barrier("0.8.9", "1.0.0"))
        self.assertFalse(policy.requires_legacy_barrier("1.0.0", "1.0.1"))

    def test_cli_writes_compact_matrix_to_github_output(self) -> None:
        policy = load_policy()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"

            exit_code = policy.main(
                [
                    "matrix",
                    "--inventory",
                    str(RELEASES),
                    "--profile-set",
                    "current",
                    "--github-output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            name, value = output.read_text(encoding="utf-8").strip().split("=", 1)
            self.assertEqual(name, "source_matrix")
            matrix = json.loads(value)
            self.assertTrue(matrix)
            self.assertIn("issue-90-duplicate", {case["label"] for case in matrix})

    def test_rejects_unknown_profile_set(self) -> None:
        policy = load_policy()

        with self.assertRaisesRegex(ValueError, "unsupported profile set"):
            policy.build_manual_cases(
                {"schemaVersion": 1, "releases": [], "fixtures": []}, "weekly"
            )


if __name__ == "__main__":
    unittest.main()
