#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "regression_analysis_final.py"
DST = ROOT / "src" / "regression_analysis_final_v2.py"

text = SRC.read_text(encoding="utf-8")

text = text.replace(
    'C2: CAR = a + b Score + controls + e      (Size, BM, Volatility, Turnover)',
    'C2: CAR = a + b Score + controls + e      (Size, BM, Volatility, Turnover, EADRet, Accruals)'
)

text = text.replace(
    'CONTROL = ROOT / "data" / "metadata" / "controls" / "controls_item7.csv"',
    'CONTROL = ROOT / "data" / "metadata" / "controls" / "controls_item7_final6.csv"'
)

old_map = '''CONTROL_CANDIDATES = {
    "size": ["size", "Size"],
    "bm": ["bm", "BM", "book_to_market"],
    "volatility": ["volatility", "Volatility", "vol"],
    "turnover": ["turnover", "Turnover"],
}'''
new_map = '''CONTROL_CANDIDATES = {
    "size": ["size", "Size"],
    "bm": ["bm", "BM", "book_to_market"],
    "volatility": ["volatility", "Volatility", "vol"],
    "turnover": ["turnover", "Turnover"],
    "eadret": ["eadret", "EADRet", "ead_ret"],
    "accruals": ["accruals", "Accruals"],
}'''
if old_map not in text:
    raise RuntimeError("CONTROL_CANDIDATES block not found.")
text = text.replace(old_map, new_map)

old_ctrl = '''    # Primary control set for this phase: the four controls that are directly defined and implementable.
    controls4 = ["size", "bm", "volatility", "turnover"]'''
new_ctrl = '''    # Locked primary control set: six controls.
    controls6 = ["size", "bm", "volatility", "turnover", "eadret", "accruals"]'''
if old_ctrl not in text:
    raise RuntimeError("controls4 block not found.")
text = text.replace(old_ctrl, new_ctrl)

text = text.replace('cols = [score] + controls4', 'cols = [score] + controls6')
text = text.replace('["lm_positive_prop","lm_negative_prop"] + controls4',
                    '["lm_positive_prop","lm_negative_prop"] + controls6')
text = text.replace('"Full_C2_Controls4"', '"Full_C2_Controls6"')
text = text.replace('label+"_Controls"', 'label+"_Controls6"')
text = text.replace('"C3_LM_Pos_Neg_Controls4"', '"C3_LM_Pos_Neg_Controls6"')

needle = '''    print(f"Merged sample: {len(df)} rows | firms={df['ticker'].nunique()}")
    print(f"Scores found: {list(scores)}")'''
replacement = '''    print(f"Merged sample: {len(df)} rows | firms={df['ticker'].nunique()}")
    print(f"Scores found: {list(scores)}")
    print("Locked C2 controls:", controls6)
    complete6 = df[controls6].apply(pd.to_numeric, errors="coerce").notna().all(axis=1)
    print(f"Complete 6-control rows: {int(complete6.sum())}/{len(df)}")'''
if needle not in text:
    raise RuntimeError("Merged-sample print block not found.")
text = text.replace(needle, replacement)

if "controls4" in text:
    raise RuntimeError("Some controls4 references remain; inspect before using.")

DST.write_text(text, encoding="utf-8")
print(f"Created: {DST}")
print("Existing HC3, firm-clustered SE, diagnostics, and result-export logic are preserved.")
