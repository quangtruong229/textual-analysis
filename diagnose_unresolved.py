from pathlib import Path
import re


CASES = {
    "DE_2025": Path(
        "data/processed/10k/DE/000110465925122321.txt"
    ),
    "SPG_2021": Path(
        "data/processed/10k/SPG/000155837021001700.txt"
    ),
}


PATTERNS = [
    r"item\s+7a?\b",
    r"item\s+8\b",
    r"management.?s\s+discussion",
    r"managements\s+discussion",
    r"financial\s+instrument",
    r"market\s+risk",
    r"market\s+risks",
    r"quantitative.*market\s+risk",
    r"qualitative.*market\s+risk",
]


def show_matches(name, path):
    print("\n" + "=" * 110)
    print(name)
    print(path)
    print("=" * 110)

    if not path.exists():
        print("FILE NOT FOUND")
        return

    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    hits = []

    combined = re.compile(
        "|".join(f"(?:{p})" for p in PATTERNS),
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        if combined.search(line):
            hits.append(i)

    # Remove duplicate nearby hits so output remains readable.
    selected = []
    for i in hits:
        if not selected or i - selected[-1] > 2:
            selected.append(i)

    print(f"Total lines: {len(lines):,}")
    print(f"Matching areas: {len(selected)}")
    print()

    for center in selected:
        lo = max(0, center - 3)
        hi = min(len(lines), center + 6)

        print("-" * 110)

        for i in range(lo, hi):
            marker = ">>>" if i == center else "   "
            text = re.sub(r"\s+", " ", lines[i]).strip()

            print(
                f"{marker} {i+1:5d}: {text}"
            )


for name, path in CASES.items():
    show_matches(name, path)
