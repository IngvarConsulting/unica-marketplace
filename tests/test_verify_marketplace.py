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

    def test_workflows_use_one_sha_verified_codex_setup(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                root / ".github/workflows/verify.yml",
                root / ".github/workflows/legacy-migration-regression.yml",
                root / ".github/workflows/legacy-migration-case.yml",
            )
        )
        action = (
            root / ".github/actions/setup-locked-codex/action.yml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("gh release download rust-v", workflows)
        self.assertGreaterEqual(
            workflows.count("uses: ./.github/actions/setup-locked-codex"), 6
        )
        self.assertIn("codex-cli-lock.json", action)
        self.assertIn("Get-FileHash", action)
        self.assertIn("CODEX_BIN=", action)

    def test_workflows_cover_full_history_and_ongoing_legacy_migration_policy(self) -> None:
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

        inventory = (
            root / ".github" / "contracts" / "legacy-releases.json"
        ).read_text(encoding="utf-8")
        for version in (
            "v0.3.3",
            "v0.3.4",
            "v0.3.5",
            "v0.3.6",
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
            self.assertIn(version, inventory)
        self.assertIn("issue-90-duplicate", inventory)
        self.assertIn("643046a111d15a1ffc13c836a930a7569b552c69", inventory)
        self.assertIn("scripts/regression_policy.py matrix", one_time)
        self.assertIn("fromJSON(needs.resolve-target.outputs.source_matrix)", one_time)
        self.assertIn("macos-15", migration_case)
        self.assertIn("ubuntu-latest", migration_case)
        self.assertIn("windows-2022", migration_case)
        self.assertIn("issue_90_marker", migration_case)
        self.assertIn("setup-locked-codex", migration_case)
        self.assertIn("$env:CODEX_BIN", migration_case)
        self.assertIn("unica-marketplace/archive/$env:SOURCE_RELEASE.tar.gz", migration_case)
        self.assertIn("source-tag", migration_case)
        self.assertNotIn("legacy-stable-upgrade:", verify)
        self.assertNotIn("issue-90-duplicate", verify)

    def test_automatic_promotion_gate_resolves_catalog_event_commit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verify = (root / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )
        migration_case = (
            root / ".github" / "workflows" / "legacy-migration-case.yml"
        ).read_text(encoding="utf-8")

        contract = verify[verify.index("  contract:"):verify.index("  resolve-migration-target:")]
        resolver = verify[
            verify.index("  resolve-migration-target:"):
            verify.index("  staged-package-smoke:")
        ]

        self.assertIn("catalog_promoted: ${{ steps.detect.outputs.catalog_promoted }}", contract)
        self.assertIn("python3 scripts/detect_promotion.py", contract)
        self.assertNotIn("catalog_changed", contract)
        self.assertNotIn("staged_plugin_changed", contract)
        self.assertIn("PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}", contract)
        self.assertIn("EVENT_SHA: ${{ github.sha }}", contract)
        self.assertIn("resolve-migration-target:", verify)
        self.assertIn("needs.contract.outputs.catalog_promoted == 'true'", resolver)
        self.assertIn("needs.contract.outputs.catalog_matches_plugin == 'true'", resolver)
        self.assertNotIn("needs.contract.outputs.catalog_changed", resolver)
        self.assertNotIn("previous_catalog_version !=", resolver)
        self.assertIn("PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}", resolver)
        self.assertIn("EVENT_SHA: ${{ github.sha }}", resolver)
        self.assertRegex(
            resolver,
            r"\$targetCommit = if \(\$env:EVENT_NAME -eq 'pull_request'\) \{\n"
            r"\s+\$env:PR_HEAD_SHA\n\s+\} else \{\n\s+\$env:EVENT_SHA",
        )
        self.assertIn("marketplace_commit=$targetCommit", resolver)
        self.assertIn("ref: ${{ steps.select.outputs.marketplace_commit }}", resolver)
        self.assertIn("EXPECTED_MARKETPLACE_COMMIT: ${{ steps.select.outputs.marketplace_commit }}", resolver)
        self.assertIn("$marketplaceCommit -ne $env:EXPECTED_MARKETPLACE_COMMIT", resolver)
        self.assertIn("did not resolve to expected event commit", resolver)
        self.assertIn("gh release view", verify)
        self.assertIn("isDraft,publishedAt,assets", verify)
        self.assertIn("Get-InstallerDigest 'install-unica.ps1'", verify)
        self.assertIn("Get-InstallerDigest 'install-unica.sh'", verify)
        self.assertIn("needs: [contract, resolve-migration-target]", verify)
        self.assertIn(
            "TARGET_MARKETPLACE_REF: ${{ needs.resolve-migration-target.outputs.marketplace_ref }}",
            verify,
        )
        self.assertIn(
            "TARGET_MARKETPLACE_COMMIT: ${{ needs.resolve-migration-target.outputs.marketplace_commit }}",
            verify,
        )
        self.assertNotIn("legacy-stable-upgrade:", verify)
        self.assertNotIn("issue-90-duplicate", verify)
        for runner in ("macos-15", "ubuntu-latest", "windows-2022"):
            self.assertIn(runner, migration_case)

    def test_automatic_gate_documents_and_enforces_the_promotion_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verify = (root / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )
        resolver = verify[
            verify.index("  resolve-migration-target:"):
            verify.index("  staged-package-smoke:")
        ]

        self.assertIn("catalog promotion boundary", resolver)
        self.assertIn("staged-plugin-only PR", resolver)
        self.assertIn("still-old catalog", resolver)
        self.assertRegex(
            resolver,
            r"github\.event_name == 'pull_request' &&\n"
            r"\s+needs\.contract\.outputs\.catalog_promoted == 'true' &&\n"
            r"\s+needs\.contract\.outputs\.catalog_matches_plugin == 'true'",
        )
        self.assertRegex(
            resolver,
            r"github\.event_name == 'push' && github\.ref == 'refs/heads/main' &&\n"
            r"\s+needs\.contract\.outputs\.catalog_promoted == 'true' &&\n"
            r"\s+needs\.contract\.outputs\.catalog_matches_plugin == 'true'",
        )
        self.assertNotIn("previous_catalog_version !=", resolver)

    def test_previous_stable_paths_pin_main_before_and_after_installation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verify = (root / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )
        seed = verify[
            verify.index("  previous-stable-seed:"):
            verify.index("  previous-stable-upgrade:")
        ]
        upgrade = verify[
            verify.index("  previous-stable-upgrade:"):
        ]

        self.assertIn("TARGET_MARKETPLACE_REF: main", seed)
        self.assertIn("TARGET_MARKETPLACE_COMMIT: ${{ github.sha }}", seed)
        self.assertIn("function Assert-MarketplaceRefAtCommit", seed)
        self.assertEqual(seed.count("Assert-MarketplaceRefAtCommit"), 3)
        first_seed_guard = seed.index("Assert-MarketplaceRefAtCommit\n", seed.index("function Assert-MarketplaceRefAtCommit") + 1)
        seed_install = seed.index("plugin marketplace add")
        last_seed_guard = seed.rindex("Assert-MarketplaceRefAtCommit")
        self.assertLess(first_seed_guard, seed_install)
        self.assertLess(seed_install, last_seed_guard)

        self.assertIn("needs: [contract, resolve-migration-target]", upgrade)
        self.assertIn("needs.resolve-migration-target.result == 'success'", upgrade)
        self.assertIn(
            "TARGET_MARKETPLACE_REF: ${{ needs.resolve-migration-target.outputs.marketplace_ref }}",
            upgrade,
        )
        self.assertIn(
            "TARGET_MARKETPLACE_COMMIT: ${{ needs.resolve-migration-target.outputs.marketplace_commit }}",
            upgrade,
        )
        self.assertIn("function Assert-MarketplaceRefAtCommit", upgrade)
        self.assertEqual(upgrade.count("Assert-MarketplaceRefAtCommit"), 3)
        first_upgrade_guard = upgrade.index("Assert-MarketplaceRefAtCommit\n", upgrade.index("function Assert-MarketplaceRefAtCommit") + 1)
        upgrade_operation = upgrade.index("plugin marketplace upgrade")
        last_upgrade_guard = upgrade.rindex("Assert-MarketplaceRefAtCommit")
        self.assertLess(first_upgrade_guard, upgrade_operation)
        self.assertLess(upgrade_operation, last_upgrade_guard)

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

        self.assertTrue(regression.startswith("name: Full legacy migration regression\n"))
        self.assertNotIn("One-time legacy migration regression", regression)
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

        self.assertIn("workflow_dispatch:", regression)
        self.assertNotIn("schedule:", regression)
        self.assertNotIn("pull_request:", regression)
        self.assertIn("profile_set:", regression)
        self.assertIn("current", regression)
        self.assertIn("barrier", regression)
        self.assertIn("manual-rollback:", regression)
        self.assertIn("rollback-succeeded", regression)
        self.assertIn("marketplace_ref:", regression)
        self.assertIn("target_version:", regression)
        self.assertIn("github.ref_name", regression)
        self.assertNotIn("github.head_ref", regression)
        self.assertNotIn("PR_HEAD_REF", regression)
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
        self.assertNotIn("immutable version tag", regression)
        self.assertNotIn("Immutable source release", regression)

        self.assertIn("Manual full-history regression", migration_guide)
        self.assertIn("Full legacy migration regression", migration_guide)
        self.assertNotIn("One-time legacy migration regression", migration_guide)
        self.assertIn("selected workflow ref", migration_guide)
        self.assertIn("published semantic-version source release", migration_guide)
        self.assertIn("captured SHA-256 digests", migration_guide)


if __name__ == "__main__":
    unittest.main()
