from pathlib import Path
from collections import Counter, defaultdict
import math
import re

import pandas as pd


# ============================================================
# PATHS
# ============================================================

V3_METADATA = Path(
    "data/metadata/sections_10k_v3.csv"
)

SECTION_DIR = Path(
    "data/sections_v3/10k"
)

LM_DICT = Path(
    "data/dictionary/Loughran-McDonald_MasterDictionary_1993-2025.xlsx"
)

HARVARD_DICT = Path(
    "data/dictionary/HIV-4.csv"
)

OUTPUT = Path(
    "data/metadata/tone_method_item7.csv"
)


# ============================================================
# SETTINGS
# ============================================================

SECTION = "item_7_mda"

NEGATORS = {
    "NOT",
    "NO",
    "NEVER",
}

WORD_RE = re.compile(
    r"[A-Za-z]+(?:[-'][A-Za-z]+)*"
)


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(text):
    return [
        x.upper()
        for x in WORD_RE.findall(
            str(text)
        )
    ]


# ============================================================
# NEGATION-AWARE COUNTS
# ============================================================

def sentiment_counts(
    tokens,
    positive_words,
    negative_words,
):
    """
    Required A1 rule from the group's method:
    do not count positive/negative words when one of
    NOT / NO / NEVER appears within the preceding 3 tokens.
    """

    counts = Counter()

    negated_positive = 0
    negated_negative = 0

    for i, word in enumerate(tokens):

        previous = tokens[
            max(0, i - 3):i
        ]

        negated = any(
            x in NEGATORS
            for x in previous
        )

        if word in positive_words:

            if negated:
                negated_positive += 1
            else:
                counts[
                    ("positive", word)
                ] += 1

        if word in negative_words:

            if negated:
                negated_negative += 1
            else:
                counts[
                    ("negative", word)
                ] += 1

    return (
        counts,
        negated_positive,
        negated_negative,
    )


# ============================================================
# DICTIONARIES
# ============================================================

def load_lm():

    df = pd.read_excel(
        LM_DICT,
        usecols=[
            "Word",
            "Negative",
            "Positive",
            "Uncertainty",
        ],
    )

    words = (
        df["Word"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    negative = set(
        words.loc[
            pd.to_numeric(
                df["Negative"],
                errors="coerce",
            ).fillna(0) > 0
        ]
    )

    positive = set(
        words.loc[
            pd.to_numeric(
                df["Positive"],
                errors="coerce",
            ).fillna(0) > 0
        ]
    )

    uncertainty = set(
        words.loc[
            pd.to_numeric(
                df["Uncertainty"],
                errors="coerce",
            ).fillna(0) > 0
        ]
    )

    return {
        "positive": positive,
        "negative": negative,
        "uncertainty": uncertainty,
    }


def load_harvard():

    df = pd.read_csv(
        HARVARD_DICT,
        low_memory=False,
        usecols=[
            "Entry",
            "Positiv",
            "Negativ",
        ],
    )

    words = (
        df["Entry"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    positive = set(
        words.loc[
            df["Positiv"].notna()
        ]
    )

    negative = set(
        words.loc[
            df["Negativ"].notna()
        ]
    )

    return {
        "positive": positive,
        "negative": negative,
    }


# ============================================================
# SECTION PATH
# ============================================================

def section_file(row):

    ticker = str(
        row["ticker"]
    ).upper()

    accession = str(
        row["accession_number"]
    ).strip()

    path = (
        SECTION_DIR
        / ticker
        / accession
        / f"{SECTION}.txt"
    )

    return path if path.exists() else None


# ============================================================
# DOCUMENT COLLECTION
# ============================================================

def load_documents(
    metadata,
):
    documents = []

    for _, row in metadata.iterrows():

        if str(
            row.get(
                f"{SECTION}_status",
                ""
            )
        ) != "success":
            continue

        path = section_file(row)

        if path is None:
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        tokens = tokenize(text)

        documents.append({
            "ticker": row["ticker"],
            "filing_date": row["filing_date"],
            "report_date": row.get(
                "report_date"
            ),
            "accession_number": row[
                "accession_number"
            ],
            "company_name": row.get(
                "company_name"
            ),
            "path": str(path),
            "tokens": tokens,
        })

    return documents


# ============================================================
# IDF
# ============================================================

def build_idf(
    documents,
    positive_words,
    negative_words,
):
    """
    J&W Eq. 1:
        idf_j = log(N / df_j)

    df_j = number of documents containing word j
    at least once after A1 negation filtering.
    """

    N = len(documents)

    document_frequency = defaultdict(int)

    lexicon = (
        positive_words
        | negative_words
    )

    for doc in documents:

        tokens = doc["tokens"]

        present = set()

        for i, word in enumerate(tokens):

            if word not in lexicon:
                continue

            previous = tokens[
                max(0, i - 3):i
            ]

            if any(
                x in NEGATORS
                for x in previous
            ):
                continue

            present.add(word)

        for word in present:
            document_frequency[word] += 1

    idf = {}

    for word, df in document_frequency.items():

        if df > 0:
            idf[word] = math.log(
                N / df
            )

    return idf


# ============================================================
# SCORE ONE DOCUMENT
# ============================================================

def calculate_scores(
    tokens,
    dictionary,
    idf,
):
    total_words = len(tokens)

    counts, neg_pos, neg_neg = sentiment_counts(
        tokens,
        dictionary["positive"],
        dictionary["negative"],
    )

    pos_counts = {
        word: count
        for (category, word), count
        in counts.items()
        if category == "positive"
    }

    neg_counts = {
        word: count
        for (category, word), count
        in counts.items()
        if category == "negative"
    }

    # --------------------------------------------------------
    # A2 proportional weighting
    # --------------------------------------------------------

    pos_count = sum(
        pos_counts.values()
    )

    neg_count = sum(
        neg_counts.values()
    )

    uncertainty_count = sum(
        1
        for i, word in enumerate(tokens)
        if (
            word
            in dictionary.get(
                "uncertainty",
                set()
            )
        )
    )

    positive_prop = (
        pos_count / total_words
        if total_words
        else None
    )

    negative_prop = (
        neg_count / total_words
        if total_words
        else None
    )

    uncertainty_prop = (
        uncertainty_count / total_words
        if total_words
        else None
    )

    # Common combined proportional definition.
    net_prop = (
        positive_prop - negative_prop
        if total_words
        else None
    )

    # Alternative ratio mentioned in the group's method.
    ratio_denominator = (
        positive_prop + negative_prop
    )

    net_ratio = (
        (
            positive_prop - negative_prop
        )
        / ratio_denominator
        if ratio_denominator
        else None
    )

    # --------------------------------------------------------
    # A3 TF-IDF
    # --------------------------------------------------------

    pos_tfidf = 0.0
    neg_tfidf = 0.0

    for word, tf in pos_counts.items():

        if word in idf:

            pos_tfidf += (
                (1.0 + math.log(tf))
                * idf[word]
            )

    for word, tf in neg_counts.items():

        if word in idf:

            neg_tfidf += (
                (1.0 + math.log(tf))
                * idf[word]
            )

    normalizer = (
        1.0 + math.log(total_words)
        if total_words > 0
        else 1.0
    )

    pos_tfidf_score = (
        pos_tfidf / normalizer
    )

    neg_tfidf_score = (
        neg_tfidf / normalizer
    )

    net_tfidf_score = (
        pos_tfidf_score
        - neg_tfidf_score
    )

    return {
        "total_words": total_words,

        "positive_count": pos_count,
        "negative_count": neg_count,
        "uncertainty_count": uncertainty_count,

        "negated_positive_count": neg_pos,
        "negated_negative_count": neg_neg,

        "positive_prop": positive_prop,
        "negative_prop": negative_prop,
        "uncertainty_prop": uncertainty_prop,

        "net_prop": net_prop,
        "net_ratio": net_ratio,

        "positive_tfidf": pos_tfidf_score,
        "negative_tfidf": neg_tfidf_score,
        "net_tfidf": net_tfidf_score,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not V3_METADATA.exists():
        raise FileNotFoundError(
            V3_METADATA
        )

    print("=" * 80)
    print("METHOD-COMPLIANT TONE SCORES")
    print("=" * 80)

    metadata = pd.read_csv(
        V3_METADATA,
        dtype={
            "accession_number": str,
        },
    )

    documents = load_documents(
        metadata
    )

    print(
        "Usable Item 7 documents:",
        len(documents),
    )

    if not documents:
        raise RuntimeError(
            "No usable Item 7 documents."
        )

    print()
    print("Loading dictionaries...")

    lm = load_lm()
    harvard = load_harvard()

    print(
        "LM Positive:",
        len(lm["positive"]),
    )
    print(
        "LM Negative:",
        len(lm["negative"]),
    )
    print(
        "Harvard Positive:",
        len(harvard["positive"]),
    )
    print(
        "Harvard Negative:",
        len(harvard["negative"]),
    )

    # --------------------------------------------------------
    # IDF
    # --------------------------------------------------------

    print()
    print("Building LM IDF...")

    lm_idf = build_idf(
        documents,
        lm["positive"],
        lm["negative"],
    )

    print(
        "LM IDF terms:",
        len(lm_idf),
    )

    print(
        "Building Harvard IDF..."
    )

    harvard_idf = build_idf(
        documents,
        harvard["positive"],
        harvard["negative"],
    )

    print(
        "Harvard IDF terms:",
        len(harvard_idf),
    )

    # --------------------------------------------------------
    # Score documents
    # --------------------------------------------------------

    rows = []

    for i, doc in enumerate(
        documents,
        start=1,
    ):

        lm_score = calculate_scores(
            doc["tokens"],
            lm,
            lm_idf,
        )

        harvard_score = calculate_scores(
            doc["tokens"],
            harvard,
            harvard_idf,
        )

        row = {
            "ticker": doc["ticker"],
            "filing_date": doc["filing_date"],
            "report_date": doc["report_date"],
            "accession_number": doc[
                "accession_number"
            ],
            "company_name": doc[
                "company_name"
            ],

            "section": "Item 7",
            "section_code": SECTION,

            "file": doc["path"],
        }

        for key, value in lm_score.items():
            row[
                f"lm_{key}"
            ] = value

        for key, value in harvard_score.items():
            row[
                f"harvard_{key}"
            ] = value

        rows.append(row)

        if i % 100 == 0:
            print(
                f"Scored {i}/"
                f"{len(documents)}"
            )

    out = pd.DataFrame(rows)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("METHOD SCORES COMPLETE")
    print("=" * 80)

    print(
        "Rows:",
        len(out),
    )

    for col in [
        "lm_positive_prop",
        "lm_negative_prop",
        "lm_net_prop",
        "lm_net_ratio",
        "lm_positive_tfidf",
        "lm_negative_tfidf",
        "lm_net_tfidf",
        "harvard_positive_prop",
        "harvard_negative_prop",
        "harvard_net_prop",
        "harvard_net_ratio",
        "harvard_positive_tfidf",
        "harvard_negative_tfidf",
        "harvard_net_tfidf",
    ]:

        print(
            f"{col:28s}",
            f"mean={out[col].mean():.8f}",
            f"median={out[col].median():.8f}",
        )

    print()
    print(
        "Mean negated LM positive:",
        out[
            "lm_negated_positive_count"
        ].mean(),
    )

    print(
        "Mean negated LM negative:",
        out[
            "lm_negated_negative_count"
        ].mean(),
    )

    print()
    print("Output:", OUTPUT)


if __name__ == "__main__":
    main()
