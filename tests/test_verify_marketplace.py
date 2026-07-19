from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_marketplace import ContractError, verify, verify_catalog


class MarketplaceContractTests(unittest.TestCase):
    def write_catalog(self, root: Path, version: str) -> None:
        catalog = root / ".agents" / "plugins" / "marketplace.json"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            json.dumps(
                {
                    "name": "unica",
                    "plugins": [
                        {
                            "name": "unica",
                            "source": {
                                "source": "git-subdir",
                                "url": "https://github.com/IngvarConsulting/unica-marketplace.git",
                                "path": "./plugins/unica",
                                "ref": f"v{version}",
                            },
                            "policy": {"installation": "AVAILABLE"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_empty_repository_is_allowed_only_before_first_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(verify(root, allow_empty=True))
            with self.assertRaisesRegex(ContractError, "plugins/unica is missing"):
                verify(root)

    def test_catalog_is_forbidden_before_plugin_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".agents" / "plugins" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"name": "unica", "plugins": []}), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "catalog cannot exist"):
                verify(root, allow_empty=True)

    def test_staged_plugin_may_be_newer_than_the_stable_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, "0.7.2")

            verify_catalog(root, "0.7.5")

    def test_staged_plugin_cannot_be_older_than_the_stable_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, "0.7.5")

            with self.assertRaisesRegex(ContractError, "older than the stable catalog"):
                verify_catalog(root, "0.7.2")

    def test_workflow_verifies_staged_package_fresh_install_and_previous_stable_update(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("staged-package-smoke:", workflow)
        self.assertIn("$pluginRoot = (Resolve-Path -LiteralPath 'plugins/unica').Path", workflow)
        self.assertIn("consumer-fresh-install:", workflow)
        self.assertIn("previous-stable-seed:", workflow)
        self.assertIn("previous-stable-upgrade:", workflow)
        self.assertIn("plugin marketplace upgrade unica --json", workflow)
        self.assertIn("plugin remove unica@unica --json", workflow)
        self.assertIn("plugin add unica@unica --json", workflow)
        self.assertIn("Node.js leaked into the consumer PATH", workflow)

    def test_workflows_cover_one_time_and_ongoing_legacy_migration_policy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        one_time = (
            root / ".github" / "workflows" / "legacy-migration-regression.yml"
        ).read_text(encoding="utf-8")
        migration_case = (
            root / ".github" / "workflows" / "legacy-migration-case.yml"
        ).read_text(encoding="utf-8")
        verify = (root / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )

        for version in (
            "v0.3.3",
            "v0.3.10",
            "v0.3.11",
            "v0.3.12",
            "v0.4.1",
            "v0.4.2",
            "v0.4.3",
            "v0.4.4",
            "v0.5.1",
            "v0.6.1",
            "v0.7.2",
        ):
            self.assertIn(version, one_time)
        self.assertIn("issue-90-duplicate", one_time)
        self.assertIn("macos-15", migration_case)
        self.assertIn("ubuntu-latest", migration_case)
        self.assertIn("windows-2022", migration_case)
        self.assertIn("issue_90_marker", migration_case)
        self.assertIn("$codexCommandName", migration_case)
        self.assertIn("'codex.exe'", migration_case)
        self.assertIn("legacy-stable-upgrade:", verify)
        self.assertIn("source_version: 0.6.1", verify)


if __name__ == "__main__":
    unittest.main()
