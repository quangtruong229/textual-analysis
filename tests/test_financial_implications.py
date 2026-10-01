"""Ensure implications follow measured coefficients and distinguish Word Power."""

import unittest

import pandas as pd

from presentation import financial_implications


class FinancialImplicationTests(unittest.TestCase):
    def test_sign_and_significance_change_the_narrative(self) -> None:
        rows = pd.DataFrame([
            {"model": "C3_CAR_0_p3_LM_PosNeg", "term": "lm_positive_prop",
             "coefficient": -1.0, "p_hc3_two_sided": .02, "p_cluster_two_sided": .03},
            {"model": "C3_CAR_0_p3_LM_PosNeg", "term": "lm_negative_prop",
             "coefficient": -.2, "p_hc3_two_sided": .4, "p_cluster_two_sided": .5},
        ])
        c2 = pd.DataFrame([{"dependent_variable": "car_0_p3", "term": "size",
                            "coefficient": .1, "p_hc3_two_sided": .01,
                            "p_cluster_two_sided": .02}])
        event = pd.DataFrame([{"window": "CAR_0_p3", "CAAR": .005}])
        narrative = financial_implications(rows, c2, event)
        self.assertIn("ngược chiều kỳ vọng", narrative)
        self.assertIn("size (dương)", narrative)
        self.assertNotIn("Word Power chưa được tính", narrative)
        rows.loc[rows.term.eq("lm_positive_prop"), "coefficient"] = 1.0
        updated = financial_implications(rows, c2, event)
        self.assertIn("cùng chiều kỳ vọng", updated)
        wp = pd.DataFrame([
            {"model": "C2_H1_WP_positive_six_controls", "term": "lm_positive_wp",
             "dependent_variable": "car_0_p3", "coefficient": -1.0,
             "p_hc3_one_sided": .9, "p_cluster_one_sided": .8, "n": 481},
            {"model": "C2_H2_WP_negative_six_controls", "term": "lm_negative_wp",
             "dependent_variable": "car_0_p3", "coefficient": .1,
             "p_hc3_one_sided": .4, "p_cluster_one_sided": .4, "n": 481},
        ])
        with_wp = financial_implications(rows, c2, event, word_power=wp)
        self.assertIn("Word Power đã được tính riêng", with_wp)


if __name__ == "__main__":
    unittest.main()
