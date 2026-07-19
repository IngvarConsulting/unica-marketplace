from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.detect_promotion import detect


class PromotionDetectionTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        return result.stdout.strip()

    def initialize(self, root: Path) -> None:
        self.git(root, "init", "-q")
        self.git(root, "config", "user.name", "Marketplace Tests")
        self.git(root, "config", "user.email", "marketplace-tests@example.invalid")

    def write_plugin(self, root: Path, version: str) -> None:
        descriptor = root / "plugins" / "unica" / ".codex-plugin" / "plugin.json"
        descriptor.parent.mkdir(parents=True, exist_ok=True)
        descriptor.write_text(json.dumps({"version": version}), encoding="utf-8")

    def write_catalog(self, root: Path, version: str, **extra: object) -> None:
        catalog = root / ".agents" / "plugins" / "marketplace.json"
        catalog.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "name": "unica",
            "plugins": [{"name": "unica", "source": {"ref": f"v{version}"}}],
            **extra,
        }
        catalog.write_text(json.dumps(document, indent=2), encoding="utf-8")

    def commit(self, root: Path, message: str) -> str:
        self.git(root, "add", ".")
        self.git(root, "commit", "-q", "-m", message)
        return self.git(root, "rev-parse", "HEAD")

    def detect_pr(self, root: Path, base: str, head: str) -> dict[str, str]:
        return detect(
            root=root,
            event_name="pull_request",
            event_ref="refs/pull/1/merge",
            event_sha="f" * 40,
            before_sha="",
            pr_base_sha=base,
            pr_head_sha=head,
        )

    def test_same_ref_json_edit_is_not_a_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            self.write_plugin(root, "1.0.0")
            self.write_catalog(root, "1.0.0")
            base = self.commit(root, "base")
            self.write_catalog(root, "1.0.0", description="format-only policy metadata")
            head = self.commit(root, "same ref")

            outputs = self.detect_pr(root, base, head)

            self.assertEqual(outputs["catalog_promoted"], "false")
            self.assertEqual(outputs["catalog_matches_plugin"], "true")
            self.assertEqual(outputs["previous_catalog_version"], "1.0.0")

    def test_source_ref_delta_is_a_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            self.write_plugin(root, "1.0.0")
            self.write_catalog(root, "1.0.0")
            base = self.commit(root, "base")
            self.write_plugin(root, "1.1.0")
            self.write_catalog(root, "1.1.0")
            head = self.commit(root, "promote")

            outputs = self.detect_pr(root, base, head)

            self.assertEqual(outputs["catalog_promoted"], "true")
            self.assertEqual(outputs["catalog_version"], "1.1.0")
            self.assertEqual(outputs["previous_catalog_version"], "1.0.0")

    def test_initial_catalog_addition_is_a_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            self.write_plugin(root, "1.0.0")
            base = self.commit(root, "stage plugin")
            self.write_catalog(root, "1.0.0")
            head = self.commit(root, "first promotion")

            outputs = self.detect_pr(root, base, head)

            self.assertEqual(outputs["catalog_promoted"], "true")
            self.assertEqual(outputs["previous_catalog_version"], "")
            self.assertEqual(outputs["catalog_version"], "1.0.0")

    def test_pull_request_uses_exact_head_tree_not_current_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            self.write_plugin(root, "1.0.0")
            self.write_catalog(root, "1.0.0")
            base = self.commit(root, "base")
            self.write_plugin(root, "1.1.0")
            self.write_catalog(root, "1.1.0")
            head = self.commit(root, "pull request head")
            self.write_plugin(root, "9.9.9")
            self.write_catalog(root, "9.9.9")
            self.commit(root, "synthetic checkout tree")

            outputs = self.detect_pr(root, base, head)

            self.assertEqual(outputs["plugin_version"], "1.1.0")
            self.assertEqual(outputs["catalog_version"], "1.1.0")
            self.assertEqual(outputs["catalog_matches_plugin"], "true")

    def test_main_push_uses_event_sha_and_before_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize(root)
            self.write_plugin(root, "1.0.0")
            self.write_catalog(root, "1.0.0")
            before = self.commit(root, "main before")
            self.write_plugin(root, "1.1.0")
            self.write_catalog(root, "1.1.0")
            event_sha = self.commit(root, "main event")
            self.write_plugin(root, "9.9.9")
            self.write_catalog(root, "9.9.9")
            self.commit(root, "later checkout tree")

            outputs = detect(
                root=root,
                event_name="push",
                event_ref="refs/heads/main",
                event_sha=event_sha,
                before_sha=before,
                pr_base_sha="",
                pr_head_sha="",
            )

            self.assertEqual(outputs["plugin_version"], "1.1.0")
            self.assertEqual(outputs["catalog_version"], "1.1.0")
            self.assertEqual(outputs["previous_catalog_version"], "1.0.0")
            self.assertEqual(outputs["catalog_promoted"], "true")


if __name__ == "__main__":
    unittest.main()
