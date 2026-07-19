from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_marketplace import ContractError, verify


class MarketplaceContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

