from pathlib import Path
import importlib.util
import pandas as pd

MODULE_PATH = Path("src/extract_sections.py")

spec = importlib.util.spec_from_file_location(
    "extract_sections_current",
    MODULE_PATH,
)

if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")

mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# Các ticker đã từng xuất hiện trong quá trình debug
TICKERS = [
    "CAH",
    "WELL",
    "FCX",
    "LRCX",
    "SPG",
    "AON",
    "DG",
    "PEG",
    "APD",
    "LYV",
    "PEP",
    "DE",
]


def section_words(lines, section):
    if section is None:
        return 0

    start = section["start"]
    end = section.get("end")

    if end is None:
        return 0

    return mod.words(" ".join(lines[start:end]))


def classify(section):
    if section is None:
        return "MISSING"

    words = section_words(
        CURRENT_LINES,
        section,
    )

    boundary = section.get("boundary_method")

    if words < 100:
        return "SHORT"

    if boundary == "uncertain":
        return "BOUNDARY_UNCERTAIN"

    return "OK"


df = pd.read_csv(
    mod.METADATA_PATH,
    dtype={"accession_number": str},
)

df["ticker"] = df["ticker"].astype(str).str.upper()
df["filing_date"] = pd.to_datetime(
    df["filing_date"],
    errors="coerce",
)

# Lấy tối đa 3 năm đại diện cho mỗi ticker:
# năm đầu, năm giữa, năm cuối trong dataset.
selected_rows = []

for ticker in TICKERS:
    sub = df[df["ticker"] == ticker].copy()

    if sub.empty:
        print(f"[WARN] No filings found for {ticker}")
        continue

    sub = sub.sort_values("filing_date")

    indices = sorted(
        set([
            sub.index[0],
            sub.index[len(sub) // 2],
            sub.index[-1],
        ])
    )

    selected_rows.append(
        sub.loc[indices]
    )

sample = pd.concat(
    selected_rows,
    ignore_index=True,
)


results = []

for _, row in sample.iterrows():

    accession = mod.normalize_accession(
        row["accession_number"]
    )

    path = mod.find_input_file(row)

    if path is None:
        results.append({
            "ticker": row["ticker"],
            "filing_date": row["filing_date"],
            "accession": accession,
            "status": "INPUT_MISSING",
        })
        continue

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    global CURRENT_LINES
    CURRENT_LINES = text.splitlines()

    extracted, diagnostics = mod.extract_filing(
        CURRENT_LINES
    )

    row_result = {
        "ticker": row["ticker"],
        "filing_date": row["filing_date"].date(),
        "accession": accession,
        "item1a_words": section_words(
            CURRENT_LINES,
            extracted.get("item_1a_risk_factors"),
        ),
        "item7_words": section_words(
            CURRENT_LINES,
            extracted.get("item_7_mda"),
        ),
        "item7a_words": section_words(
            CURRENT_LINES,
            extracted.get("item_7a_market_risk"),
        ),
        "item1a_status": classify(
            extracted.get("item_1a_risk_factors")
        ),
        "item7_status": classify(
            extracted.get("item_7_mda")
        ),
        "item7a_status": classify(
            extracted.get("item_7a_market_risk")
        ),
    }

    results.append(row_result)


out = pd.DataFrame(results)

print("\n" + "=" * 110)
print("SECTION VALIDATION SAMPLE")
print("=" * 110)

print(
    out.to_string(
        index=False
    )
)

print("\n" + "=" * 110)
print("STATUS SUMMARY")
print("=" * 110)

for col in [
    "item1a_status",
    "item7_status",
    "item7a_status",
]:
    print(f"\n{col}")
    print(
        out[col]
        .value_counts(dropna=False)
        .to_string()
    )

print("\n" + "=" * 110)
print("FILES TESTED:", len(out))
print("=" * 110)

out.to_csv(
    "data/metadata/section_validation_sample.csv",
    index=False,
)

print(
    "\nSaved:"
    "\ndata/metadata/section_validation_sample.csv"
)
