from pathlib import Path
import argparse
import re

import pandas as pd


# ============================================================
# PATHS
# ============================================================

METADATA_PATH = Path("data/metadata/preprocessed_10k.csv")
PROCESSED_DIR = Path("data/processed/10k")
SECTIONS_DIR = Path("data/sections/10k")
OUTPUT_METADATA = Path("data/metadata/sections_10k.csv")


# ============================================================
# TARGETS
# ============================================================

TARGETS = {
    "item_1a_risk_factors": {
        "item": "1A",
        "titles": [
            "Risk Factors",
        ],
        "heading_patterns": [
            r"^Risk Factors(?:$|[.:;\-–—])",
        ],
        "fallbacks": [],
        "min_words": 100,
    },
    "item_7_mda": {
        "item": "7",
        "titles": [
            "Management's Discussion and Analysis of Financial Condition and Results of Operations",
            "Management's Discussion and Analysis of Financial Condition and Results of Operation",
            "Management's Discussion and Analysis",
            "Managements Discussion and Analysis of Financial Condition and Results of Operations",
            "Managements Discussion and Analysis of Financial Condition and Results of Operation",
            "Managements Discussion and Analysis",
            "Management's Discussion Analysis",
            "Managements Discussion Analysis",
            "Management's Discussion and Analysis of Financial Condition and Results of Operations (MD&A)",
            "Managements Discussion and Analysis of Financial Condition and Results of Operations (MD&A)",
        ],
        "heading_patterns": [
            r"^Management.?s Discussion and Analysis(?:$|[.:;\-–—]|\s*\([^)]{1,20}\)\s*$)",
        ],
        "fallbacks": [
            r"^The following discussion and analysis\b",
            r"^This section of this Form 10-K generally discusses\b",
        ],
        "min_words": 200,
    },
    "item_7a_market_risk": {
        "item": "7A",
        "titles": [
            "Quantitative and Qualitative Disclosures About Market Risk",
            "Quantitative and Qualitative Disclosures About Market Risks",
            "Disclosures About Market Risk",
            "Disclosures about Market Risk",
            "Disclosures About Market Risks",
            "Disclosures about Market Risks",
            "Market Risk",
            "Market Risks",
            "Market Risk Information",
            "Financial Instrument Market Risk Information",
            "Qualitative and Quantitative Disclosure About Market Risk",
            "Qualitative and Quantitative Disclosures About Market Risk",
            "Qualitative and Quantitative Disclosures About Market Risks",
        ],
        "heading_patterns": [
            r"^Quantitative and Qualitative Disclosures About Market Risks?(?:$|[.:;\-–—])",
            r"^Disclosures About Market Risks?(?:$|[.:;\-–—])",
            r"^Market Risks?(?:$|[.:;\-–—])",
            r"^Financial Instrument Market Risk Information(?:$|[.:;\-–—])",
            r"^Market Risk Information(?:$|[.:;\-–—])",
        ],
        "boundary_titles": [
            "Business",
        ],
        "fallbacks": [],
        "min_words": 30,
    },
}


ITEM_RE = re.compile(
    r"^\s*Items?\s+([0-9]+A?)"
    r"\s*(?:[.:;]|-|–|—)?\s*(.*)$",
    re.IGNORECASE,
)

COMBINED_7_7A_RE = re.compile(
    r"^\s*Items?\s+7\s*\.\s*and\s*7A\s*\.",
    re.IGNORECASE,
)


# ============================================================
# V11 CHANGES
# ============================================================
# 1. Narrow generic TOC detection so a real body heading immediately after
#    the contents page is not rejected as TOC material (CAH-type filings).
# 2. Add a conservative structural Item-number boundary fallback for title
#    variants, so Item 7 can still end at a genuine Item 8 heading (DE-type
#    filings) without treating a market-risk subsection as Item 7A.
#
# V17 changes:
# 5. Ignore sentence-level lowercase "financial statements" fragments as Item 8 boundaries.
#
# V18 changes:
# 6. Recognize split Item headers such as "Item" followed by "7A. ...".
# 7. Accept fragmented MD&A headings such as "MANAGEMENT'S / DISCUSSION / ANALYSIS".
# 8. Accept common SPG-style "Qualitative and Quantitative Disclosure About Market Risk" wording.
# 9. Prefer a later substantive Market Risk section when an earlier formal Item 7A is only a pointer.
#
# V13 changes:
# 3. Accept the common "(MD&A)" suffix on a genuine MD&A heading (CAH-type
#    filings).
# 4. Rework structural boundary selection so repeated TOC/page-reference
#    rows cannot prematurely truncate a real Item 7 (PEP-type filings).


# ============================================================
# NORMALIZATION
# ============================================================

def norm(text):
    text = str(text)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def norm_title(text):
    text = norm(text).lower()
    text = re.sub(r'^[\s\[\("]+', "", text)
    text = re.sub(r'[\s\]\)",:;.]+$', "", text)
    return text


def words(text):
    return len(re.findall(r"\b[\w'-]+\b", text))


def item_number(line):
    m = ITEM_RE.match(norm(line))
    return m.group(1).upper() if m else None


def item_remainder(line):
    m = ITEM_RE.match(norm(line))
    return m.group(2).strip() if m else ""


def combined_7_7a(line):
    return bool(
        COMBINED_7_7A_RE.match(
            norm(line)
        )
    )


# ============================================================
# TITLE / CONTEXT HELPERS
# ============================================================

def joined(lines, start, width):
    return norm_title(
        " ".join(
            lines[
                start : min(
                    len(lines),
                    start + width,
                )
            ]
        )
    )


def matches_title(
    lines,
    start,
    titles,
    max_lines=5,
):
    """
    Match a heading by exact normalized text across up to max_lines.

    IMPORTANT: this must not use substring matching. A phrase such as
    "Risk Factors" appearing inside ordinary prose is a cross-reference,
    not a section heading.
    """
    wanted = {
        norm_title(t)
        for t in titles
    }

    for width in range(
        1,
        max_lines + 1,
    ):
        candidate = joined(
            lines,
            start,
            width,
        )

        if candidate in wanted:
            return True

    return False


def matched_title_word_count(
    lines,
    start,
    titles,
    max_lines=5,
):
    """
    Return the number of words in the longest exact title match.

    This is used to prefer a complete/specific fragmented heading over
    a shorter valid title that starts in the middle of the same heading.
    """
    wanted = {
        norm_title(t)
        for t in titles
    }

    best = 0

    for width in range(
        1,
        max_lines + 1,
    ):
        candidate = joined(
            lines,
            start,
            width,
        )

        if candidate in wanted:
            best = max(
                best,
                len(candidate.split()),
            )

    return best


SPLIT_ITEM_RE = re.compile(
    r"^\s*([0-9]+A?)"
    r"\s*(?:[.:;]|-|–|—)?\s*(.*)$",
    re.IGNORECASE,
)


def split_item_parts(lines, start):
    """Parse a two-line item header such as: Item / 7A. Title."""
    if norm(lines[start]).lower() not in {"item", "items"}:
        return None, "", None

    nxt = next_nonempty(lines, start + 1)
    if nxt is None:
        return None, "", None

    m = SPLIT_ITEM_RE.match(norm(lines[nxt]))
    if not m:
        return None, "", None

    return m.group(1).upper(), m.group(2).strip(), nxt


def contextual_item_number(lines, start):
    detected = item_number(lines[start])
    if detected is not None:
        return detected

    detected, _, _ = split_item_parts(lines, start)
    return detected


def contextual_item_remainder(lines, start):
    remainder = item_remainder(lines[start])
    if remainder:
        return remainder

    _, split_remainder, _ = split_item_parts(lines, start)
    return split_remainder


def explicit_item_matches_title(
    lines,
    start,
    config,
):
    """Match Item X when the title is on the same line or following lines."""
    remainder = norm(contextual_item_remainder(lines, start))

    # Item 7. Management's Discussion...
    if remainder:
        for width in range(1, 5):
            candidate = norm_title(
                " ".join(
                    [
                        remainder,
                        *[
                            norm(lines[j])
                            for j in range(
                                start + 1,
                                min(len(lines), start + width),
                            )
                            if norm(lines[j])
                        ],
                    ]
                )
            )
            if candidate in {norm_title(t) for t in config["titles"]}:
                return True
        return False

    # Item 7.
    # Management's Discussion...
    nxt = next_nonempty(lines, start + 1)
    return nxt is not None and matches_title(
        lines,
        nxt,
        config["titles"],
    )


def next_nonempty(lines, start):
    for i in range(
        start,
        len(lines),
    ):
        if norm(lines[i]):
            return i
    return None


def is_formal_item_method(method):
    return method in {
        "explicit_item",
        "explicit_item_fallback",
        "combined_item_7_7a",
        "explicit_item_colon",
    }


def is_body_candidate(lines, candidate):
    """Return True when candidate is not strongly associated with TOC/index text."""
    start = candidate["start"]
    return not (
        looks_like_index_table_context(lines, start)
        or looks_like_toc_or_index_context(lines, start)
    )


def long_prose_count(
    lines,
    start,
    lookahead=15,
):
    end = min(
        len(lines),
        start + lookahead,
    )
    total = 0

    for i in range(
        start + 1,
        end,
    ):
        line = norm(lines[i])
        if (
            len(line) >= 70
            and re.search(
                r"[A-Za-z]{3,}",
                line,
            )
        ):
            total += 1

    return total


def nearby_contains(
    lines,
    start,
    patterns,
    lookahead=15,
):
    end = min(
        len(lines),
        start + lookahead,
    )

    for i in range(
        start,
        end,
    ):
        text = norm(lines[i])

        for pattern in patterns:
            if re.search(
                pattern,
                text,
                re.IGNORECASE,
            ):
                return True

    return False


def looks_like_index_table_context(lines, start):
    """Detect late Form 10-K cross-reference/index tables.

    These blocks often contain a run of section names plus standalone item
    numbers (e.g. 7A, 9A, 9B) and N/A markers, but do not contain prose.
    They are especially dangerous because the text is identical to the real
    section titles and can otherwise outscore the true body heading.
    """
    lo = max(0, start - 8)
    hi = min(len(lines), start + 12)

    window = [norm(lines[i]) for i in range(lo, hi) if norm(lines[i])]
    if not window:
        return False

    before = " ".join(window[: max(1, min(10, len(window))) ]).lower()
    after_lines = window[max(0, start - lo):]

    bare_codes = 0
    na_count = 0
    for t in after_lines:
        if re.fullmatch(r"[0-9]+A?", t, re.IGNORECASE):
            bare_codes += 1
        if t.upper() == "N/A":
            na_count += 1

    has_part_ii = any(t.lower() == "part ii" for t in window)
    section_list_markers = sum(
        1
        for t in window
        if re.fullmatch(
            r"(?:Part II|Part III|N/A|[0-9]+A?)",
            t,
            re.IGNORECASE,
        )
    )

    # Strong signature of a cross-reference/index table.  Requiring at least
    # two bare item codes avoids flagging normal body prose.
    if bare_codes >= 2 and (has_part_ii or na_count >= 1):
        return True

    if section_list_markers >= 4 and (has_part_ii or na_count >= 1):
        return True

    return False


def looks_like_toc_or_index_context(lines, start):
    """Flag candidates that are genuinely embedded in TOC/index material."""
    # Only use a short lookback for strong index markers. A full-page / 40-line
    # lookback can incorrectly classify a genuine body heading that appears
    # shortly after the Table of Contents (e.g. CAH 2019 line 117).
    context_start = max(0, start - 12)
    context_end = min(len(lines), start + 1)
    context = " ".join(
        norm(lines[i]).lower()
        for i in range(context_start, context_end)
        if norm(lines[i])
    )

    strong_markers = [
        "form 10-k cross reference index",
        "cross reference index",
        "cross-reference index",
        "form 10-k cross-reference",
    ]
    if any(marker in context for marker in strong_markers):
        return True

    recent_back_start = max(0, start - 18)
    recent_lookback = " ".join(
        norm(lines[i]).lower()
        for i in range(recent_back_start, start)
        if norm(lines[i])
    )

    nearby_items = sum(
        1
        for i in range(start, min(len(lines), start + 12))
        if item_number(lines[i])
    )
    prose = long_prose_count(lines, start, lookahead=12)

    has_generic_toc_marker = (
        "table of contents" in recent_lookback
        or "contents" in recent_lookback
    )
    if has_generic_toc_marker and nearby_items >= 2 and prose == 0:
        return True

    # A dense run of Item headings is TOC-like only when the candidate has
    # no substantive prose immediately following it. Real body sections
    # can legitimately be adjacent, e.g. Item 7A followed by Item 8.
    if nearby_items >= 3 and prose == 0:
        return True

    return False

def looks_like_substantive_heading(lines, start, config):
    """Allow an explicit Item X fallback when the title wording is nonstandard."""
    if looks_like_toc_or_index_context(lines, start):
        return False

    remainder = norm(contextual_item_remainder(lines, start))
    remainder_lower = remainder.lower()

    # Explicit 'Not applicable' / 'Reserved' sections are legitimate headings.
    if re.search(r"\bnot applicable\b|\breserved\b", remainder_lower):
        return True

    # A recognizable section family on the same line or nearby lines is enough.
    if re.search(
        r"management.?s discussion and analysis|risk factors|market risk|quantitative and qualitative",
        remainder,
        re.IGNORECASE,
    ):
        return True

    # Split-heading form: inspect the next few non-empty lines.
    nxt = next_nonempty(lines, start + 1)
    if nxt is None:
        return False

    window = []
    for i in range(nxt, min(len(lines), nxt + 6)):
        text = norm(lines[i])
        if text:
            window.append(text)

    window_text = " ".join(window)

    if re.search(
        r"management.?s discussion and analysis|risk factors|market risk|quantitative and qualitative|not applicable|reserved",
        window_text,
        re.IGNORECASE,
    ):
        return True

    # A body section often begins with substantial prose immediately after Item X.
    prose = long_prose_count(lines, start, lookahead=10)
    return prose >= 2


def heading_pattern_match(lines, start, patterns):
    if not patterns:
        return False

    text = norm(lines[start])
    # Heading-pattern fallbacks are intentionally limited to short lines to
    # avoid treating ordinary prose beginning with the same words as a heading.
    if len(text) > 140:
        return False

    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


# ============================================================
# CANDIDATES
# ============================================================

def candidates_for(
    lines,
    config,
):
    result = []
    target_item = config["item"]

    for i, raw in enumerate(lines):

        line = norm(raw)

        if not line:
            continue

        detected_item = contextual_item_number(lines, i)

        # Combined Items 7 and 7A.
        if target_item == "7" and combined_7_7a(line):
            remainder = re.sub(
                r"^\s*Items?\s+7\s*\.\s*and\s*7A\s*\.\s*",
                "",
                line,
                flags=re.IGNORECASE,
            )

            mda_titles = {norm_title(t) for t in config["titles"]}
            remainder_norm = norm_title(remainder)

            if any(
                remainder_norm.startswith(t)
                for t in mda_titles
            ):
                result.append(
                    {
                        "start": i,
                        "method": "combined_item_7_7a",
                    }
                )
                continue

        # Explicit Item heading.
        if detected_item == target_item:
            matched = explicit_item_matches_title(
                lines,
                i,
                config,
            )

            if matched:
                colon_form = (
                    ":" in line
                    and "." not in line
                )

                result.append(
                    {
                        "start": i,
                        "method": (
                            "explicit_item_colon"
                            if colon_form
                            else "explicit_item"
                        ),
                    }
                )
            elif looks_like_substantive_heading(
                lines,
                i,
                config,
            ):
                result.append(
                    {
                        "start": i,
                        "method": "explicit_item_fallback",
                    }
                )

        # Title-only heading.
        if matches_title(
            lines,
            i,
            config["titles"],
        ):
            result.append(
                {
                    "start": i,
                    "method": "title_only",
                }
            )

        # Heading-pattern fallback for nonstandard title wording.
        if heading_pattern_match(
            lines,
            i,
            config.get("heading_patterns", []),
        ):
            result.append(
                {
                    "start": i,
                    "method": "heading_pattern",
                }
            )

        # Prose fallback (primarily Item 7).
        for pattern in config["fallbacks"]:
            if re.search(
                pattern,
                line,
                re.IGNORECASE,
            ):
                result.append(
                    {
                        "start": i,
                        "method": "fallback_prose",
                    }
                )

    return result


def score_candidate(
    lines,
    candidate,
    config,
):
    start = candidate["start"]
    method = candidate["method"]

    score = 0.0
    line = norm(lines[start])

    base = {
        "combined_item_7_7a": 24,
        "explicit_item": 19,
        "explicit_item_fallback": 15,
        "title_only": 13,
        "heading_pattern": 11,
        "fallback_prose": 9,
        "explicit_item_colon": 2,
    }

    score += base.get(
        method,
        0,
    )

    title_word_count = matched_title_word_count(
        lines,
        start,
        config["titles"],
    )

    if title_word_count:
        score += 8

        # V19:
        # Prefer the most specific/full title when a longer fragmented
        # heading contains a shorter valid title starting later.
        #
        # Example:
        #   FINANCIAL
        #   INSTRUMENT
        #   MARKET
        #   RISK
        #   INFORMATION
        #
        # should beat:
        #   MARKET
        #   RISK
        #   INFORMATION
        score += min(
            title_word_count,
            10,
        )

    prose = long_prose_count(
        lines,
        start,
    )
    score += min(
        prose,
        7,
    )

    # Strong TOC / index heuristics.
    nearby_items = sum(
        1
        for i in range(
            start,
            min(
                len(lines),
                start + 12,
            ),
        )
        if item_number(lines[i])
    )

    if looks_like_index_table_context(lines, start):
        score -= 30
    elif looks_like_toc_or_index_context(lines, start):
        score -= 25
    elif nearby_items >= 2:
        # Formal Item headings inside the filing body may be adjacent to
        # other Items. Keep the penalty small for those candidates.
        if is_formal_item_method(method):
            score -= 3
        else:
            score -= 18

    # Early candidates are especially likely to be TOC entries when the
    # filing immediately lists several Item headings around them.
    if start < 250 and nearby_items >= 2:
        score -= 8

    nxt = next_nonempty(
        lines,
        start + 1,
    )

    if (
        nxt is not None
        and item_number(lines[nxt])
    ):
        score -= 8

    # Colon form is usually a cross-reference.
    if method == "explicit_item_colon":
        score -= 12

    # WELL-style actual MD&A anchor.
    if (
        config["item"] == "7"
        and method == "fallback_prose"
    ):
        if nearby_contains(
            lines,
            start,
            [
                r"^Executive Summary$",
                r"^EXECUTIVE SUMMARY$",
            ],
            lookahead=12,
        ):
            score += 9

        if nearby_contains(
            lines,
            start,
            [r"^Company Overview$"],
            lookahead=15,
        ):
            score += 5

    # Very early candidates are more likely TOC entries, but do not penalize
    # them if they are clearly substantive.
    if start < 110:
        score -= 8

    if start >= 300 and not looks_like_toc_or_index_context(lines, start):
        score += 3

    # An explicit Item candidate that survived the structural fallback is useful
    # even when the exact title wording is nonstandard.
    if method == "explicit_item_fallback":
        score += 2

    # A heading-pattern candidate should be backed by prose or a valid short
    # section marker such as 'Not applicable'.
    if method == "heading_pattern":
        if long_prose_count(lines, start) > 0:
            score += 3
        remainder = norm(contextual_item_remainder(lines, start)).lower()
        if "not applicable" in remainder or "reserved" in remainder:
            score += 3

    # A heading-like candidate with no prose is suspicious.
    if (
        method != "fallback_prose"
        and prose == 0
    ):
        score -= 6

    return score


def best_candidate(
    lines,
    config,
):
    raw_candidates = candidates_for(
        lines,
        config,
    )

    scored = []

    for candidate in raw_candidates:
        item = dict(candidate)
        item["score"] = score_candidate(
            lines, candidate, config
        )
        item["line"] = candidate["start"] + 1
        item["preview"] = norm(lines[candidate["start"]])
        item["body_candidate"] = is_body_candidate(lines, candidate)
        scored.append(item)

    if not scored:
        return None, []

    # --------------------------------------------------------
    # Formal Item headings are the strongest evidence of the actual
    # section.  Do not discard them merely because nearby Item headings
    # make the local context look TOC-like.  The score still penalizes
    # obvious TOC/cross-reference forms.
    # --------------------------------------------------------
    formal = [
        c for c in scored
        if is_formal_item_method(c["method"])
        and c["method"] != "explicit_item_colon"
        and c["score"] >= 7
    ]

    if formal:
        formal.sort(
            key=lambda x: (x["score"], -x["start"]),
            reverse=True,
        )
        best = formal[0]
    else:
        # For title-only / heading-pattern candidates, strongly prefer
        # candidates outside obvious TOC/index material.
        body_scored = [
            c for c in scored
            if c["body_candidate"]
        ]

        if body_scored:
            working = body_scored
        else:
            working = scored

        working.sort(
            key=lambda x: (x["score"], -x["start"]),
            reverse=True,
        )
        best = working[0]

    prose = long_prose_count(lines, best["start"])

    # A genuine title-only body heading may score below 7 but can still be
    # accepted when it is followed by substantive prose.
    if best["score"] < 7:
        if (
            best["body_candidate"]
            and prose >= 2
            and best["method"] in {
                "title_only",
                "heading_pattern",
                "fallback_prose",
            }
        ):
            pass
        else:
            return None, sorted(
                scored,
                key=lambda x: (x["score"], -x["start"]),
                reverse=True,
            )

    return best, sorted(
        scored,
        key=lambda x: (x["score"], -x["start"]),
        reverse=True,
    )


# ============================================================
# GENERIC ITEM BOUNDARIES
# ============================================================

END_TITLES = {
    "1B": [
        "Unresolved Staff Comments",
    ],
    "1C": [
        "Cybersecurity",
    ],
    "2": [
        "Properties",
    ],
    "3": [
        "Legal Proceedings",
    ],
    "4": [
        "Mine Safety Disclosures",
    ],
    "5": [
        "Market for Registrant's Common Equity",
        "Market for Registrant’s Common Equity",
    ],
    "6": [
        "Selected Financial Data",
    ],
    "8": [
        "Financial Statements and Supplementary Data",
        "Financial Statements and Supplementary Data and Reports",
        "Financial Statements",
    ],
    "9": [
        "Changes in and Disagreements with Accountants",
    ],
    "9A": [
        "Controls and Procedures",
    ],
}


def title_boundary(
    lines,
    start,
    titles,
):
    """Find the first exact standalone heading from *titles* after start."""
    if not titles:
        return None

    for i in range(start + 1, len(lines)):
        if matches_title(
            lines,
            i,
            titles,
        ):
            return i

    return None


def looks_like_structural_item_heading(lines, start, config):
    """
    Conservative fallback for an explicit structural Item number when the
    issuer uses a title variant not covered by END_TITLES.

    We require body-like context so an Item number in a TOC/index is not used
    as the boundary.
    """
    if looks_like_toc_or_index_context(lines, start):
        return False

    remainder = norm(contextual_item_remainder(lines, start))

    # A short non-empty remainder on an isolated Item heading is useful, but
    # reject obvious TOC/page-reference fragments.
    if remainder:
        if len(remainder) <= 140 and not re.search(
            r"\b(page|pages|table of contents|cross reference|index)\b",
            remainder,
            re.IGNORECASE,
        ):
            return True

    # Split-heading form: Item X on one line, structural title immediately
    # after it, even when the exact title wording differs from END_TITLES.
    nxt = next_nonempty(lines, start + 1)
    if nxt is not None:
        window = []
        for i in range(nxt, min(len(lines), nxt + 5)):
            text = norm(lines[i])
            if text:
                window.append(text)

        window_text = " ".join(window)
        if re.search(
            r"financial statements?|supplementary data|financial condition|"
            r"legal proceedings|properties|controls and procedures|"
            r"selected financial data|unresolved staff comments|"
            r"cybersecurity|mine safety|changes in and disagreements",
            window_text,
            re.IGNORECASE,
        ):
            return True

    # Last-resort body evidence for non-standard structural headings.
    return long_prose_count(lines, start, lookahead=10) >= 2


def financial_statement_boundary(lines, start):
    """Find the first strong financial-statement title after *start*."""
    patterns = [
        r"^statement of consolidated income$",
        r"^statement of consolidated comprehensive income$",
        r"^consolidated statement of operations$",
        r"^consolidated statements of operations$",
        r"^consolidated statement of income$",
        r"^consolidated statements of income$",
        r"^deere & company statement of consolidated income$",
        r"^consolidated balance sheet$",
        r"^consolidated statements of cash flows$",
        r"^statement of cash flows$",
    ]

    for i in range(start + 1, len(lines)):
        text = norm(lines[i])
        if not text:
            continue
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return i
    return None


def probable_toc_structural_candidate(lines, start, allowed_items):
    """Reject structural Item headings that look like TOC/page-reference rows."""
    if looks_like_toc_or_index_context(lines, start):
        return True

    # Page numbers often appear immediately after a TOC row.
    numeric_only = 0
    for i in range(start + 1, min(len(lines), start + 4)):
        t = norm(lines[i])
        if not t:
            continue
        if re.fullmatch(r"(?:page\\s*)?\\d{1,4}(?:[-–—]\\d{1,4})?", t, re.IGNORECASE):
            numeric_only += 1

    if numeric_only > 0:
        return True

    # A dense run of Item headings with no substantive prose is TOC-like.
    nearby_items = sum(
        1
        for i in range(start, min(len(lines), start + 10))
        if item_number(lines[i])
    )
    prose = long_prose_count(lines, start, lookahead=10)
    if nearby_items >= 3 and prose == 0:
        return True

    return False


def structural_boundary(
    lines,
    start,
    allowed_items,
):
    """
    Find the next structural section boundary without trusting a TOC row.

    The old implementation returned the first plausible Item X.  That is
    dangerous when a repeated table-of-contents block appears inside the
    filing: Item 8 in that block can prematurely truncate Item 7.

    We collect plausible boundaries first, reject strong TOC/page-reference
    candidates, then choose the earliest remaining body-like boundary.
    """
    allowed = {x.upper() for x in allowed_items}
    formal_candidates = []
    title_candidates = []

    for i in range(start + 1, len(lines)):
        detected = item_number(lines[i])

        if detected in allowed:
            end_config = {
                "item": detected,
                "titles": END_TITLES.get(detected, []),
            }

            if probable_toc_structural_candidate(lines, i, allowed):
                continue

            if explicit_item_matches_title(
                lines,
                i,
                end_config,
            ):
                formal_candidates.append(i)
                continue

            if looks_like_structural_item_heading(
                lines,
                i,
                end_config,
            ):
                formal_candidates.append(i)
                continue

        for item in allowed:
            if matches_title(
                lines,
                i,
                END_TITLES.get(item, []),
            ):
                # Generic "Financial Statements" is also a common phrase
                # inside ordinary prose.  Do not treat a lowercase sentence
                # fragment such as "provided for in the consolidated
                # financial statements." as an Item 8 boundary.  A real
                # standalone title normally starts with an uppercase letter.
                if item == "8":
                    raw = norm(lines[i]).strip()
                    stripped = raw.rstrip(" .:;-")
                    if (
                        stripped.lower() == "financial statements"
                        and (not stripped or not stripped[0].isupper())
                    ):
                        continue

                if probable_toc_structural_candidate(lines, i, allowed):
                    continue
                title_candidates.append(i)

    if formal_candidates:
        return min(formal_candidates)

    if title_candidates:
        return min(title_candidates)

    return None


def next_candidate_start_after(
    diagnostics,
    name,
    start,
):
    """Return the earliest plausible candidate for a target after start."""
    candidates = [
        c for c in diagnostics.get(name, [])
        if c["start"] > start
    ]

    if not candidates:
        return None

    # Earliest exact heading after the current section is the safest
    # boundary; it avoids jumping to a later repeated heading.
    candidates.sort(key=lambda c: c["start"])
    return candidates[0]["start"]


def best_candidate_after(
    diagnostics,
    name,
    start,
):
    """Choose the best-scoring target candidate after start."""
    candidates = [
        c for c in diagnostics.get(name, [])
        if c["start"] > start
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (c.get("score", 0), -c["start"]),
        reverse=True,
    )
    return candidates[0]


def first_later_start(
    candidate_starts,
    start,
):
    later = [
        x["start"]
        for x in candidate_starts.values()
        if x is not None
        and x["start"] > start
    ]

    return (
        min(later)
        if later
        else None
    )


# ============================================================
# EXTRACT ONE FILING
# ============================================================

def candidate_is_pointer_like(lines, candidate):
    """Return True when a formal Item candidate is mostly a pointer/reference."""
    start = candidate["start"]
    if not is_formal_item_method(candidate["method"]):
        return False

    chunks = []
    seen = 0
    for i in range(start, min(len(lines), start + 7)):
        t = norm(lines[i])
        if not t:
            continue
        chunks.append(t.lower())
        seen += 1
        if seen >= 5:
            break

    text = " ".join(chunks)
    markers = [
        "see the information",
        "see information",
        "included in",
        "incorporated by reference",
        "beginning on page",
        "pages ",
        "required information is",
    ]
    return any(marker in text for marker in markers)


def choose_relocated_body_candidate(lines, diagnostics, name, formal_candidate):
    """Choose a later substantive heading when the formal Item is only a pointer."""
    if formal_candidate is None or not candidate_is_pointer_like(lines, formal_candidate):
        return formal_candidate

    start = formal_candidate["start"]
    candidates = [
        c for c in diagnostics.get(name, [])
        if c["start"] > start
        and c.get("body_candidate", False)
        and c["method"] in {"title_only", "heading_pattern", "fallback_prose"}
        and long_prose_count(lines, c["start"]) >= 2
        and c.get("start", 0) - start <= 1000
    ]

    if not candidates:
        return formal_candidate

    candidates.sort(key=lambda c: (c.get("score", 0), -c["start"]), reverse=True)
    return candidates[0]


def candidate_is_toc_like(lines, candidate, target_item=None):
    """Return True when a candidate is embedded in TOC/index material."""
    start = candidate["start"]

    if looks_like_index_table_context(lines, start):
        return True
    if looks_like_toc_or_index_context(lines, start):
        return True
    if target_item is not None and probable_toc_structural_candidate(
        lines, start, {str(target_item).upper()}
    ):
        return True
    return False


def choose_item7a_candidate(lines, diagnostics, item7):
    """Select Item 7A using document structure rather than raw score alone."""
    if item7 is None:
        return None

    candidates = diagnostics.get("item_7a_market_risk", [])

    # Formal Item 7A candidates after Item 7.  Keep these as the preferred
    # representation when they are the actual 7A entry.  However, if the
    # formal entry is only a pointer and a later substantive market-risk
    # heading exists, prefer the later substantive section.
    formal_after = [
        c for c in candidates
        if c["start"] > item7["start"]
        and is_formal_item_method(c["method"])
        and c["method"] != "explicit_item_colon"
        and not candidate_is_toc_like(lines, c, "7A")
    ]

    substantive_after = [
        c for c in candidates
        if c["start"] > item7["start"]
        and c.get("body_candidate", False)
        and not candidate_is_toc_like(lines, c, "7A")
        and c["method"] in {"title_only", "heading_pattern", "fallback_prose"}
        and long_prose_count(lines, c["start"]) >= 2
    ]

    if formal_after:
        formal_after.sort(
            key=lambda c: (c.get("score", 0), -c["start"]),
            reverse=True,
        )
        formal = formal_after[0]

        # A pointer-like formal Item 7A that appears before a later
        # substantive market-risk heading is a relocation/index reference.
        # This pattern occurs in filings such as DE.
        if candidate_is_pointer_like(lines, formal):
            later_substantive = [
                c for c in substantive_after
                if c["start"] > formal["start"]
            ]
            if later_substantive:
                later_substantive.sort(
                    key=lambda c: (c.get("score", 0), -c["start"]),
                    reverse=True,
                )
                return later_substantive[0]

        return formal

    if substantive_after:
        substantive_after.sort(
            key=lambda c: (c.get("score", 0), -c["start"]),
            reverse=True,
        )
        return substantive_after[0]

    # Last resort: a formal pointer before the substantive Item 7 body.
    formal_before = [
        c for c in candidates
        if c["start"] < item7["start"]
        and is_formal_item_method(c["method"])
        and c["method"] != "explicit_item_colon"
        and not candidate_is_toc_like(lines, c, "7A")
        and candidate_is_pointer_like(lines, c)
    ]
    if formal_before:
        formal_before.sort(
            key=lambda c: (c.get("score", 0), -c["start"]),
            reverse=True,
        )
        return formal_before[0]

    return None


def extract_filing(lines):
    best = {}
    diagnostics = {}

    for name, config in TARGETS.items():
        candidate, all_candidates = best_candidate(
            lines,
            config,
        )
        best[name] = candidate
        diagnostics[name] = all_candidates

    # Some older filings place a formal Item 7/7A entry in an index-like
    # cross-reference block and give the substantive discussion elsewhere in
    # the document.  When the formal entry explicitly points to pages/another
    # caption, prefer the later substantive heading.
    if best["item_7_mda"] is not None:
        relocated = choose_relocated_body_candidate(
            lines,
            diagnostics,
            "item_7_mda",
            best["item_7_mda"],
        )
        if relocated is not None:
            best["item_7_mda"] = relocated

    if best["item_7a_market_risk"] is not None:
        relocated_7a = choose_relocated_body_candidate(
            lines,
            diagnostics,
            "item_7a_market_risk",
            best["item_7a_market_risk"],
        )
        if relocated_7a is not None:
            best["item_7a_market_risk"] = relocated_7a

    # Item 7A selection is structural: formal Item 7A after the substantive
    # Item 7 wins unless it is clearly a TOC/index entry; otherwise use a
    # substantive market-risk heading, then a relocated pointer fallback.
    item7 = best["item_7_mda"]
    if item7 is not None:
        selected_7a = choose_item7a_candidate(
            lines,
            diagnostics,
            item7,
        )
        if selected_7a is not None:
            best["item_7a_market_risk"] = selected_7a

    extracted = {}

    # --------------------------------------------------------
    # Item 1A
    # --------------------------------------------------------
    item1a = best["item_1a_risk_factors"]

    if item1a is not None:
        start = item1a["start"]

        end = structural_boundary(
            lines,
            start,
            {"1B", "1C", "2", "3", "4"},
        )
        boundary_method = (
            "structural_item"
            if end is not None
            else "uncertain"
        )

        if end is None:
            later = first_later_start(
                {
                    name: best[name]
                    for name in (
                        "item_7_mda",
                        "item_7a_market_risk",
                    )
                },
                start,
            )
            if later is not None:
                end = later
                boundary_method = "target_section_fallback"

        extracted["item_1a_risk_factors"] = {
            "start": start,
            "end": end,
            "candidate": item1a,
            "boundary_method": boundary_method,
        }

    # --------------------------------------------------------
    # Item 7
    # --------------------------------------------------------
    item7 = best["item_7_mda"]
    item7a = best["item_7a_market_risk"]

    if item7 is not None:
        start = item7["start"]
        possible_ends = []

        if item7a is not None and item7a["start"] > start:
            possible_ends.append((item7a["start"], "item_7a_start"))

        item8 = structural_boundary(lines, start, {"8"})
        if item8 is not None:
            possible_ends.append((item8, "item_8"))

        if possible_ends:
            end, boundary_method = min(
                possible_ends,
                key=lambda x: x[0],
            )
        else:
            later = first_later_start(
                {
                    "item_1a": best["item_1a_risk_factors"],
                    "item_7a": item7a,
                },
                start,
            )
            if later is not None:
                end = later
                boundary_method = "target_section_fallback"
            else:
                end = None
                boundary_method = "uncertain"

        extracted["item_7_mda"] = {
            "start": start,
            "end": end,
            "candidate": item7,
            "boundary_method": boundary_method,
        }

    # --------------------------------------------------------
    # Item 7A
    # --------------------------------------------------------
    if item7a is not None:
        start = item7a["start"]

        # For issuers that omit the explicit Item 8 heading, a named major
        # section can be a stronger boundary than simply running to EOF.
        # CAH 2025 is the motivating case: the market-risk section is
        # followed by the main "Business" section before the later
        # "Risk Factors" section.
        named_boundary = title_boundary(
            lines,
            start,
            TARGETS["item_7a_market_risk"].get(
                "boundary_titles",
                [],
            ),
        )

        item8 = structural_boundary(
            lines,
            start,
            {"8"},
        )

        possible_ends = []

        if named_boundary is not None and named_boundary > start:
            possible_ends.append(
                (named_boundary, "named_section_title")
            )

        if item8 is not None and item8 > start:
            possible_ends.append(
                (item8, "item_8")
            )

        # Generic financial-statement title is a conservative fallback when
        # Item 8 itself is not explicitly present in the cleaned text.
        statement_boundary = financial_statement_boundary(lines, start)
        if statement_boundary is not None and statement_boundary > start:
            possible_ends.append(
                (statement_boundary, "financial_statement_title")
            )

        if possible_ends:
            end, boundary_method = min(
                possible_ends,
                key=lambda x: x[0],
            )
        else:
            # Use the earliest detected later target heading. This is crucial
            # for filings such as CAH where Item 8 is not expressed as a
            # standard explicit Item heading in the cleaned text.
            later = min(
                [
                    x
                    for x in (
                        next_candidate_start_after(
                            diagnostics,
                            "item_1a_risk_factors",
                            start,
                        ),
                        next_candidate_start_after(
                            diagnostics,
                            "item_7_mda",
                            start,
                        ),
                    )
                    if x is not None
                ],
                default=None,
            )

            if later is not None:
                end = later
                boundary_method = "target_section_fallback"
            else:
                end = None
                boundary_method = "uncertain"

        extracted["item_7a_market_risk"] = {
            "start": start,
            "end": end,
            "candidate": item7a,
            "boundary_method": boundary_method,
        }

    return extracted, diagnostics


# ============================================================
# FILE LOCATION
# ============================================================

def find_input_file(row):
    ticker = str(
        row["ticker"]
    ).upper()

    accession = normalize_accession(
        row["accession_number"]
    )

    directory = (
        PROCESSED_DIR / ticker
    )

    exact = (
        directory
        / f"{accession}.txt"
    )

    if exact.exists():
        return exact

    matches = list(
        directory.glob(
            f"{accession}*.txt"
        )
    )

    return matches[0] if matches else None


# ============================================================
# PROCESS ONE ROW
# ============================================================

def process_one(row):

    ticker = str(
        row["ticker"]
    ).upper()

    accession = normalize_accession(
        row["accession_number"]
    )

    accession_clean = accession

    input_file = find_input_file(row)

    result = {
        "ticker": ticker,
        "filing_date": row.get(
            "filing_date"
        ),
        "report_date": row.get(
            "report_date"
        ),
        "accession_number": accession,
        "company_name": row.get(
            "company_name"
        ),
        "input_file": (
            str(input_file)
            if input_file
            else ""
        ),
        "status": "failed",
        "error": "",
    }

    for name in TARGETS:

        result[
            f"{name}_status"
        ] = "heading_not_found"

        result[
            f"{name}_start_line"
        ] = None

        result[
            f"{name}_end_line"
        ] = None

        result[
            f"{name}_words"
        ] = 0

        result[
            f"{name}_chars"
        ] = 0

        result[
            f"{name}_method"
        ] = ""

        result[
            f"{name}_boundary_method"
        ] = ""

        result[
            f"{name}_score"
        ] = None

        result[
            f"{name}_file"
        ] = ""

    if input_file is None:
        result[
            "error"
        ] = "processed_file_not_found"
        return result

    try:

        text = input_file.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = text.splitlines()

        extracted, diagnostics = extract_filing(
            lines
        )

        output_dir = (
            SECTIONS_DIR
            / ticker
            / accession_clean
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Remove stale section outputs.
        for name in TARGETS:
            old = (
                output_dir
                / f"{name}.txt"
            )
            if old.exists():
                old.unlink()

        for name, payload in extracted.items():

            start = payload["start"]
            end = payload["end"]
            candidate = payload["candidate"]

            if end is None:
                # We found a heading but cannot validate the end.
                result[
                    f"{name}_status"
                ] = "boundary_uncertain"

                result[
                    f"{name}_start_line"
                ] = start + 1

                result[
                    f"{name}_method"
                ] = candidate["method"]

                result[
                    f"{name}_boundary_method"
                ] = payload[
                    "boundary_method"
                ]

                result[
                    f"{name}_score"
                ] = candidate["score"]

                continue

            section_text = "\n".join(
                lines[start:end]
            ).strip()

            section_words = words(
                section_text
            )

            minimum = TARGETS[
                name
            ]["min_words"]

            # Additional contamination guard:
            # if a later target section heading appears inside the
            # extracted region, mark the result uncertain.
            contamination = False

            for other_name, other_payload in extracted.items():

                if other_name == name:
                    continue

                other_start = other_payload["start"]

                if (
                    other_start > start
                    and other_start < end
                ):
                    contamination = True
                    break

            if contamination:
                status = (
                    "boundary_uncertain"
                )
            elif section_words < minimum:
                status = "too_short"
            else:
                status = "success"

            output_file = (
                output_dir
                / f"{name}.txt"
            )

            output_file.write_text(
                section_text,
                encoding="utf-8",
            )

            result[
                f"{name}_status"
            ] = status

            result[
                f"{name}_start_line"
            ] = start + 1

            result[
                f"{name}_end_line"
            ] = end

            result[
                f"{name}_words"
            ] = section_words

            result[
                f"{name}_chars"
            ] = len(section_text)

            result[
                f"{name}_method"
            ] = candidate["method"]

            result[
                f"{name}_boundary_method"
            ] = payload[
                "boundary_method"
            ]

            result[
                f"{name}_score"
            ] = candidate["score"]

            result[
                f"{name}_file"
            ] = str(output_file)

        result[
            "status"
        ] = "success"

    except Exception as exc:
        result[
            "error"
        ] = str(exc)

    return result


# ============================================================
# ACCESSION NORMALIZATION
# ============================================================

def normalize_accession(value):
    """Normalize SEC accession to 18-digit form without dashes."""
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    # Handle values accidentally loaded by pandas as floats/scientific notation.
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]

    # If scientific notation is present, convert carefully through Decimal.
    if "e" in text.lower():
        try:
            from decimal import Decimal
            text = format(Decimal(text), "f")
            if "." in text:
                text = text.split(".", 1)[0]
        except Exception:
            pass

    digits = re.sub(r"[^0-9]", "", text)

    if not digits:
        return ""

    # SEC accession numbers are 18 digits when dashes are removed.
    return digits.zfill(18)


# ============================================================
# SELECT ROWS
# ============================================================

def select_rows(
    df,
    args,
):

    if args.accession:
        target_accession = normalize_accession(args.accession)
        accession_series = df["accession_number"].map(
            normalize_accession
        )
        subset = df[
            accession_series == target_accession
        ]

    elif args.ticker:
        subset = df[
            df["ticker"]
            .astype(str)
            .str.upper()
            == args.ticker.upper()
        ]

    elif args.test:
        subset = df[
            df["ticker"]
            .astype(str)
            .str.upper()
            == "AAPL"
        ].iloc[:1]

    else:
        subset = df

    if subset.empty:
        raise ValueError(
            "No filing matched the selection."
        )

    return subset


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Conservative 10-K section extractor "
            "for Item 1A, Item 7 and Item 7A."
        )
    )

    parser.add_argument(
        "--test",
        action="store_true",
    )

    parser.add_argument(
        "--ticker",
        type=str,
    )

    parser.add_argument(
        "--accession",
        type=str,
    )

    parser.add_argument(
        "--all",
        action="store_true",
    )

    args = parser.parse_args()

    if not any(
        [
            args.test,
            args.ticker,
            args.accession,
            args.all,
        ]
    ):
        parser.error(
            "Choose --test, --ticker, "
            "--accession, or --all."
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {METADATA_PATH}"
        )

    df = pd.read_csv(
        METADATA_PATH,
        dtype={"accession_number": str},
    )

    subset = select_rows(
        df,
        args,
    )

    print("=" * 60)
    print("SECTION EXTRACTION")
    print("=" * 60)
    print(
        f"Files to process: {len(subset)}"
    )

    current_results = []

    for idx, (_, row) in enumerate(
        subset.iterrows(),
        start=1,
    ):

        ticker = str(
            row["ticker"]
        ).upper()

        accession = str(
            row["accession_number"]
        )

        print(
            f"[{idx}/{len(subset)}] "
            f"{ticker:<6} "
            f"{accession}"
        )

        current_results.append(
            process_one(row)
        )

    current_df = pd.DataFrame(
        current_results
    )

    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    OUTPUT_METADATA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        OUTPUT_METADATA.exists()
        and not args.all
    ):

        old_df = pd.read_csv(
            OUTPUT_METADATA,
            dtype={"accession_number": str},
        )

        current_accessions = set(
            current_df[
                "accession_number"
            ]
            .astype(str)
        )

        old_df = old_df[
            ~old_df[
                "accession_number"
            ]
            .astype(str)
            .isin(
                current_accessions
            )
        ]

        saved_df = pd.concat(
            [
                old_df,
                current_df,
            ],
            ignore_index=True,
        )

    else:
        saved_df = current_df.copy()

    saved_df.to_csv(
        OUTPUT_METADATA,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("SECTION EXTRACTION COMPLETE")
    print("=" * 60)

    print(
        f"Filings processed : "
        f"{len(current_df)}"
    )

    print(
        "Success           : "
        f"{(current_df['status'] == 'success').sum()}"
    )

    print(
        "Failed            : "
        f"{(current_df['status'] == 'failed').sum()}"
    )

    for name in TARGETS:

        status_col = f"{name}_status"
        words_col = f"{name}_words"

        print()
        print(name)

        print(
            "  success          : "
            f"{(current_df[status_col] == 'success').sum()}"
        )

        print(
            "  too_short        : "
            f"{(current_df[status_col] == 'too_short').sum()}"
        )

        print(
            "  boundary_uncertain: "
            f"{(current_df[status_col] == 'boundary_uncertain').sum()}"
        )

        print(
            "  missing          : "
            f"{(current_df[status_col] == 'heading_not_found').sum()}"
        )

        print(
            "  words            : "
            f"{current_df[words_col].fillna(0).sum()}"
        )

    print()
    print("Metadata saved:")
    print(
        OUTPUT_METADATA
    )


if __name__ == "__main__":
    main()
