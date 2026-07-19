from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.legacy_migration_fixture import FixtureError, prepare_fixture


class LegacyMigrationFixtureTests(unittest.TestCase):
    def make_archive(
        self,
        root: Path,
        version: str,
        *,
        include_marketplace: bool = True,
    ) -> Path:
        archive = root / f"unica-{version}.tar.gz"
        files = {
            "release/plugins/unica/.codex-plugin/plugin.json": json.dumps(
                {"name": "unica", "version": version}
            ).encode(),
            "release/plugins/unica/.mcp.json": b'{"mcpServers": {}}',
        }
        if include_marketplace:
            files["release/.agents/plugins/marketplace.json"] = json.dumps(
                {
                    "name": "unica",
                    "plugins": [
                        {
                            "name": "unica",
                            "source": {"source": "local", "path": "./plugins/unica"},
                        }
                    ],
                }
            ).encode()
        with tarfile.open(archive, "w:gz") as package:
            for name, contents in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(contents)
                package.addfile(info, io.BytesIO(contents))
        return archive

    def test_alias_layout_matches_legacy_installer_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex-home"

            report = prepare_fixture(
                self.make_archive(root, "0.6.1"),
                codex_home,
                "0.6.1",
                "legacy-alias",
            )

            self.assertEqual(report["pluginIds"], ["unica@unica-local"])
            self.assertTrue(
                (
                    codex_home
                    / "plugins/cache/unica-local/unica/0.6.1/.codex-plugin/plugin.json"
                ).is_file()
            )
            self.assertTrue(
                (codex_home / "marketplaces/unica-local/.agents/plugins/marketplace.json").is_file()
            )
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('[marketplaces.unica]', config)
            self.assertIn('[plugins."unica@unica-local"]', config)

    def test_duplicate_layout_reproduces_issue_90_and_preserves_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex-home"

            report = prepare_fixture(
                self.make_archive(root, "0.6.1"),
                codex_home,
                "0.6.1",
                "issue-90-duplicate",
            )

            self.assertEqual(
                report["pluginIds"], ["unica@unica", "unica@unica-local"]
            )
            self.assertTrue(
                (codex_home / "plugins/cache/unica/unica/0.6.1/.mcp.json").is_file()
            )
            self.assertTrue(
                (codex_home / "plugins/cache/unica-local/unica/0.6.1/.mcp.json").is_file()
            )
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('[plugins."unica@unica"]', config)
            self.assertIn('[plugins."unica@unica-local"]', config)
            self.assertIn('issue_90_marker = "preserve-me"', config)

    def test_canonical_layouts_distinguish_local_and_git_marketplaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_home = root / "legacy-home"
            marketplace_home = root / "marketplace-home"

            prepare_fixture(
                self.make_archive(root, "0.3.3"),
                legacy_home,
                "0.3.3",
                "legacy-canonical",
            )
            prepare_fixture(
                self.make_archive(root, "0.7.2", include_marketplace=False),
                marketplace_home,
                "0.7.2",
                "marketplace-canonical",
            )

            self.assertTrue(
                (legacy_home / "marketplaces/unica-local/plugins/unica").is_dir()
            )
            self.assertTrue(
                (legacy_home / "plugins/cache/unica/unica/0.3.3").is_dir()
            )
            self.assertFalse((marketplace_home / "marketplaces/unica-local").exists())
            self.assertTrue(
                (marketplace_home / "plugins/cache/unica/unica/0.7.2").is_dir()
            )
            config = (marketplace_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('source_type = "git"', config)
            self.assertIn(
                'source = "https://github.com/IngvarConsulting/unica-marketplace.git"',
                config,
            )
            self.assertIn('ref = "main"', config)

    def test_rejects_archive_whose_plugin_version_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FixtureError, "expected plugin version 0.6.1"):
                prepare_fixture(
                    self.make_archive(root, "0.5.1"),
                    root / "codex-home",
                    "0.6.1",
                    "legacy-alias",
                )


if __name__ == "__main__":
    unittest.main()
