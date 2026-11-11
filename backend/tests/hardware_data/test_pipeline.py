import unittest
from copy import deepcopy
from decimal import Decimal

from app.domains.hardware.ingestion.common import DATA, price_value, read_json, sql_time
from app.domains.hardware.ingestion.import_compatibility import validate_records
from app.domains.hardware.ingestion.import_parts import normalize_parts, reviewed_price
from app.domains.hardware.ingestion.price_page import parse_component_price_page


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matches = read_json(DATA / "part_matches.json")["parts"]
        cls.evidence = read_json(DATA / "raw/manufacturer/compatibility_review.json")["records"]

    def price_fixture(self):
        match = {
            "danawa_product_code": "123",
            "expected_listing_name": "G.SKILL non-RGB 32GB",
            "price_basis": "COMPONENT_ONLY",
            "price_basis_source_url": "https://example.com/review",
        }
        records = [
            {
                "queried_at_utc": "2026-11-11T05:00:00Z",
                "response": {
                    "ok": True,
                    "items": [
                        {
                            "productCode": "123",
                            "productName": "G.SKILL non-RGB 32GB",
                            "minPrice": 123456,
                        }
                    ],
                },
            }
        ]
        return match, records

    def test_exact_code_and_name_price(self):
        m, r = self.price_fixture()
        self.assertEqual(reviewed_price(m, r)[0]["value"], "123456")

    def test_same_name_wrong_code_is_rejected(self):
        m, r = self.price_fixture()
        r[0]["response"]["items"][0]["productCode"] = "456"
        self.assertIsNone(reviewed_price(m, r)[0])

    def test_rgb_variant_never_replaces_non_rgb(self):
        m, r = self.price_fixture()
        r[0]["response"]["items"][0]["productName"] = "G.SKILL RGB 32GB"
        self.assertEqual(reviewed_price(m, r)[1], "LISTING_NAME_CHANGED")

    def test_unknown_shipping_basis_withholds_price(self):
        m, r = self.price_fixture()
        m["price_basis"] = "UNVERIFIED"
        self.assertEqual(reviewed_price(m, r)[1], "PRICE_BASIS_UNVERIFIED")

    def test_invalid_prices_are_not_zero_or_positive_defaults(self):
        for value in (None, False, 0, -1, "NaN", "Infinity", "bad", "10000000000000", "0.001"):
            with self.subTest(value=value):
                self.assertIsNone(price_value(value))
        self.assertEqual(price_value("123.45"), Decimal("123.45"))

    def test_latest_listing_name_change_blocks_old_match(self):
        m, r = self.price_fixture()
        newer = deepcopy(r[0])
        newer["queried_at_utc"] = "2026-11-11T06:00:00Z"
        newer["response"]["items"][0]["productName"] = "Different hardware"
        self.assertEqual(reviewed_price(m, [*r, newer])[1], "LISTING_NAME_CHANGED")

    def test_timezone_is_explicit_and_normalized(self):
        self.assertEqual(sql_time("2026-11-11T15:00:00+09:00"), sql_time("2026-11-11T06:00:00Z"))
        with self.assertRaises(ValueError):
            sql_time("2026-11-11T06:00:00")

    def test_initial_selection_and_unknown_product_exclusion(self):
        catalog = read_json(DATA / "raw/pc_builder/2026-11-11/pc-builder-parts.json")
        specs = read_json(DATA / "raw/manufacturer/pilot_specs_review.json")
        rows, withheld = normalize_parts(catalog, self.matches, specs, [], "2026-11-11T06:00:00Z")
        self.assertEqual(len(rows), 28)
        self.assertEqual(len(withheld), 3)
        by_key = {r["source_key"]: r for r in rows}
        self.assertNotIn("supp-ram-samsung16", by_key)
        self.assertNotIn("gpu-rtx-5060-ti-16gb", by_key)
        self.assertEqual(
            by_key["qvl-samsung-m323r2ga3db0-cwmod"]["model_number"], "M323R2GA3DB0-CWMOD"
        )
        self.assertEqual(by_key["mb-b650-tomahawk"]["specs"]["ram_max_gb"], 256)
        self.assertEqual(by_key["psu-850w-gold"]["specs"]["form_factor"], "ATX")
        self.assertEqual(by_key["psu-850w-gold"]["specs"]["atx_version"], "3.1")
        self.assertEqual(by_key["psu-msi-mpg-a850gs-pcie5"]["specs"]["gpu16"], 1)
        self.assertNotIn("pcie_5_connectors", by_key["psu-msi-mpg-a850gs-pcie5"]["specs"])
        self.assertTrue(all(r["current_price"] is None for r in rows))

    def test_reviewed_evidence_is_consistent(self):
        self.assertEqual(len(validate_records(self.evidence, self.matches)), 21)
        self.assertEqual(sum(r["check_type"] == "CPU_SUPPORT" for r in self.evidence), 12)

    def test_qvl_test_bios_is_not_a_minimum(self):
        records = deepcopy(self.evidence)
        ram = next(r for r in records if r["check_type"] == "MEMORY_QVL")
        ram["bios_scope"] = "MIN_VERSION"
        ram["min_bios_version"] = "3.50"
        with self.assertRaises(ValueError):
            validate_records(records, self.matches)

    def test_similar_mpn_is_rejected(self):
        records = deepcopy(self.evidence)
        next(r for r in records if r["check_type"] == "MEMORY_QVL")["conditions"][
            "ram_model_number"
        ] += "W"
        with self.assertRaises(ValueError):
            validate_records(records, self.matches)

    def test_duplicate_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_records([*self.evidence, self.evidence[0]], self.matches)

    def test_shipping_is_not_added_to_component_price(self):
        m, r = self.price_fixture()
        page = '<meta property="og:title" content="[다나와] G.SKILL non-RGB 32GB"><li data-productcode="123"></li><input id="add_delivery" checked><div class="sell-price" data-base-price="120000" data-delivery-price="3000"></div>'
        evidence = parse_component_price_page(page, m)
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["component_price"], "120000")
        r[0]["price_evidence"] = {
            **evidence,
            "source_url": "https://prod.danawa.com/info/?pcode=123",
            "checked_at_utc": "2026-11-11T06:00:00Z",
        }
        self.assertEqual(reviewed_price(m, r)[0]["value"], "120000")

    def test_missing_base_price_never_estimates_by_subtraction(self):
        m, _ = self.price_fixture()
        page = '<meta property="og:title" content="[다나와] G.SKILL non-RGB 32GB"><li data-productcode="123"></li><input id="add_delivery"><div class="sell-price">123000</div>'
        self.assertFalse(parse_component_price_page(page, m)["verified"])


if __name__ == "__main__":
    unittest.main()
