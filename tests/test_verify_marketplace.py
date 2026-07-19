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
        self.assertIn("643046a111d15a1ffc13c836a930a7569b552c69", one_time)
        self.assertIn("macos-15", migration_case)
        self.assertIn("ubuntu-latest", migration_case)
        self.assertIn("windows-2022", migration_case)
        self.assertIn("issue_90_marker", migration_case)
        self.assertIn("$codexCommandName", migration_case)
        self.assertIn("'codex.exe'", migration_case)
        self.assertIn("unica-marketplace/archive/$env:SOURCE_RELEASE.tar.gz", migration_case)
        self.assertIn("legacy-stable-upgrade:", verify)
        self.assertIn("source_version: 0.6.1", verify)
        self.assertIn("layout: issue-90-duplicate", verify)

    def test_manual_full_history_regression_pins_the_selected_commit_and_verified_installer_assets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        regression = (
            root / ".github" / "workflows" / "legacy-migration-regression.yml"
        ).read_text(encoding="utf-8")
        migration_case = (
            root / ".github" / "workflows" / "legacy-migration-case.yml"
        ).read_text(encoding="utf-8")
        verify = (root / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        migration_guide = (root / "MIGRATION.md").read_text(encoding="utf-8")

        self.assertIn("target_marketplace_ref:", migration_case)
        self.assertIn("target_marketplace_commit:", migration_case)
        self.assertIn("TARGET_MARKETPLACE_REF: ${{ inputs.target_marketplace_ref }}", migration_case)
        self.assertIn("TARGET_MARKETPLACE_COMMIT: ${{ inputs.target_marketplace_commit }}", migration_case)
        self.assertIn("-Ref $env:TARGET_MARKETPLACE_REF", migration_case)
        self.assertIn("--ref $env:TARGET_MARKETPLACE_REF", migration_case)
        self.assertNotIn("-Ref main", migration_case)
        self.assertNotIn("--ref main", migration_case)
        self.assertIn("function Assert-MarketplaceRefAtCommit", migration_case)
        self.assertIn("git ls-remote", migration_case)
        self.assertEqual(migration_case.count("Assert-MarketplaceRefAtCommit"), 5)
        self.assertRegex(
            migration_case,
            r"target_marketplace_commit:\n\s+required: true\n\s+type: string",
        )
        self.assertRegex(
            migration_case,
            r"if \(\$remoteCommit -ne \$env:TARGET_MARKETPLACE_COMMIT\) \{\n"
            r"\s+throw \"Marketplace ref \$refName moved",
        )
        first_guard = migration_case.index("Assert-MarketplaceRefAtCommit\n          if ($env:TARGET -eq 'win-x64')")
        first_install = migration_case.index("$migrationText = (& $env:INSTALLER_PATH")
        first_post_guard = migration_case.index("Assert-MarketplaceRefAtCommit", first_install)
        second_guard = migration_case.index("Assert-MarketplaceRefAtCommit\n          if ($env:TARGET -eq 'win-x64')", first_post_guard + 1)
        second_install = migration_case.index("$rerunText = (& $env:INSTALLER_PATH")
        second_post_guard = migration_case.index("Assert-MarketplaceRefAtCommit", second_install)
        self.assertLess(first_guard, first_install)
        self.assertLess(first_install, first_post_guard)
        self.assertLess(second_guard, second_install)
        self.assertLess(second_install, second_post_guard)
        self.assertIn("Get-FileHash -LiteralPath $installerPath -Algorithm SHA256", migration_case)
        self.assertIn("TARGET_INSTALLER_PS1_SHA256", migration_case)
        self.assertIn("TARGET_INSTALLER_SH_SHA256", migration_case)
        self.assertRegex(
            migration_case,
            r"\$actualInstallerSha256 -ne \$expectedInstallerSha256\) \{\n"
            r"\s+throw \"Downloaded \$installerName SHA-256",
        )

        self.assertIn("schedule:", regression)
        self.assertIn("cron: '0 0 * * 0'", regression)
        self.assertIn("marketplace_ref:", regression)
        self.assertIn("target_version:", regression)
        self.assertIn("github.ref_name", regression)
        self.assertIn("github.head_ref", regression)
        self.assertIn("PR_HEAD_REF", regression)
        self.assertRegex(
            regression,
            r"elseif \(\$env:EVENT_NAME -eq 'pull_request'\) \{\n\s+\$env:PR_HEAD_REF",
        )
        self.assertIn("actions/checkout@v4", regression)
        self.assertIn("git rev-parse HEAD", regression)
        self.assertIn("marketplace_commit", regression)
        self.assertIn("gh release view", regression)
        self.assertIn("isDraft", regression)
        self.assertIn("publishedAt", regression)
        self.assertIn("assets", regression)
        self.assertIn("digest", regression)
        self.assertNotIn("isImmutable", regression)
        self.assertRegex(
            regression,
            r"if \(\$release\.isDraft -or \[string\]::IsNullOrWhiteSpace\(\[string\]\$release\.publishedAt\)\) \{",
        )
        self.assertRegex(
            regression,
            r"\$installerPs1Sha256 = Get-InstallerDigest 'install-unica\.ps1'\n"
            r"\s+\$installerShSha256 = Get-InstallerDigest 'install-unica\.sh'",
        )
        self.assertRegex(
            regression,
            r'"marketplace_commit=\$marketplaceCommit" \| Out-File -FilePath \$env:GITHUB_OUTPUT -Append',
        )
        self.assertIn("target_marketplace_commit: ${{ needs.resolve-target.outputs.marketplace_commit }}", regression)
        self.assertIn("target_installer_ps1_sha256: ${{ needs.resolve-target.outputs.installer_ps1_sha256 }}", regression)
        self.assertIn("target_installer_sh_sha256: ${{ needs.resolve-target.outputs.installer_sh_sha256 }}", regression)
        self.assertIn("target_marketplace_ref: ${{ needs.resolve-target.outputs.marketplace_ref }}", regression)
        self.assertIn("target_version: ${{ needs.resolve-target.outputs.target_version }}", regression)
        self.assertIn("target_marketplace_commit: ${{ github.sha }}", verify)
        self.assertIn("target_marketplace_ref: main", verify)
        self.assertRegex(verify, r"target_installer_ps1_sha256: [0-9a-f]{64}")
        self.assertRegex(verify, r"target_installer_sh_sha256: [0-9a-f]{64}")

        self.assertIn("Manual full-history regression", migration_guide)
        self.assertIn("selected workflow ref", migration_guide)
        self.assertIn("published semantic-version source release", migration_guide)
        self.assertIn("captured SHA-256 digests", migration_guide)


if __name__ == "__main__":
    unittest.main()
