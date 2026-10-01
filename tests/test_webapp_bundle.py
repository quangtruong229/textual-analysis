"""Ensure the committed static bundle reflects the current research outputs."""

import csv
import contextlib
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


class WebappBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = (ROOT / "webapp/data.js").read_text(encoding="utf-8")
        cls.bundle = json.loads(source.split("window.APP_DATA = ", 1)[1].rsplit(";", 1)[0])

    def test_manifest_and_extended_results_are_current(self) -> None:
        self.assertEqual(
            self.bundle["manifest"],
            json.loads((ROOT / "handoff/manifest.json").read_text(encoding="utf-8")),
        )
        tables = {
            "firmYear": "analysis_outputs/tone_firm_year.csv",
            "c2": "analysis_outputs/c2_reduced_results.csv",
            "c2Full6": "analysis_outputs/c2_full6_results.csv",
            "c2Matched4": "analysis_outputs/c2_matched4_results.csv",
            "wordPower": "analysis_outputs/word_power/regression_results.csv",
            "b6": "analysis_outputs/event_study/b6_robustness_tests.csv",
            "brownWarner": "analysis_outputs/event_study/extended_window_tests.csv",
            "c5Full6": "analysis_outputs/c5_full6_results.csv",
            "c6": "analysis_outputs/c6_delayed_results.csv",
            "c7": "analysis_outputs/c7_cross_section_results.csv",
            "c8": "analysis_outputs/c8_fama_macbeth_summary.csv",
        }
        for key, path in tables.items():
            with self.subTest(table=key):
                self.assertEqual(len(self.bundle[key]), len(rows(path)))

    def test_displayed_sample_sizes_and_dictionary_means(self) -> None:
        original = rows("analysis_outputs/tone_firm_year.csv")[0]
        self.assertEqual(self.bundle["firmYear"][0]["accession_number"], original["accession_number"])
        self.assertEqual(self.bundle["firmYear"][0]["cik"], original["cik"])
        c2 = next(row for row in self.bundle["c2"] if row["term"] == "lm_net_prop")
        full6 = next(row for row in self.bundle["c2Full6"] if row["term"] == "lm_net_prop")
        self.assertEqual((c2["n"], c2["n_firms"]), (862, 96))
        self.assertEqual((full6["n"], full6["n_firms"]), (481, 71))
        summary = rows("analysis_outputs/dictionary_comparison_summary.csv")[0]
        for key in ("n_comparable_filings", "n_opposite_sign", "mean_lm_net_prop", "mean_harvard_net_prop"):
            with self.subTest(metric=key):
                self.assertAlmostEqual(float(self.bundle["dictSummary"][key]), float(summary[key]))

    def test_bundle_matches_a_fresh_build(self) -> None:
        spec = importlib.util.spec_from_file_location("build_data", ROOT / "webapp/build_data.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Đối chiếu trong bộ nhớ để không phụ thuộc quyền ghi thư mục tạm.
        with patch.object(Path, "write_text") as write, contextlib.redirect_stdout(io.StringIO()):
            module.main()
        fresh = json.loads(write.call_args.args[0].split("window.APP_DATA = ", 1)[1].rsplit(";", 1)[0])
        committed = dict(self.bundle)
        committed.pop("generatedAt")
        fresh.pop("generatedAt")
        self.assertEqual(committed, fresh)

    def test_source_integrity_distinguishes_content_from_line_endings(self) -> None:
        spec = importlib.util.spec_from_file_location("build_data", ROOT / "webapp/build_data.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lf = b"ticker,value\nABC,12\n"
        crlf = lf.replace(b"\n", b"\r\n")
        digest = lambda raw: hashlib.sha256(raw).hexdigest()
        self.assertEqual(module.compare_source_bytes(lf, digest(lf))["status"], "exact")
        self.assertEqual(module.compare_source_bytes(lf, digest(crlf))["status"], "line_endings_only")
        self.assertEqual(module.compare_source_bytes(crlf, digest(lf))["status"], "line_endings_only")
        self.assertEqual(module.compare_source_bytes(lf.replace(b"12", b"13"), digest(lf))["status"], "mismatch")
        self.assertEqual(module.source_integrity({"absent-source-for-test.csv": digest(lf)})[
            "absent-source-for-test.csv"]["status"], "missing")

    def test_extended_ui_options_have_data(self) -> None:
        html = (ROOT / "webapp/index.html").read_text(encoding="utf-8")
        selector = re.search(r'<select id="extended-model">(.*?)</select>', html, re.DOTALL)
        self.assertIsNotNone(selector)
        keys = re.findall(r'<option value="([^"]+)">', selector.group(1))
        self.assertEqual(len(keys), 9)
        for key in keys:
            with self.subTest(model=key):
                self.assertTrue(self.bundle[key])
        self.assertIn('id="extended-table"', html)
        self.assertIn('id="dict-interpretation"', html)


if __name__ == "__main__":
    unittest.main()
