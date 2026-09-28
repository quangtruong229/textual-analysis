from pathlib import Path
import argparse
import importlib.util
import pandas as pd

MODULE_PATH = Path('src/extract_sections.py')
spec = importlib.util.spec_from_file_location('extract_sections_current', MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f'Cannot load {MODULE_PATH}')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DEFAULT_ACCESSIONS = [
    '000072137119000090',  # CAH 2019
    '000007747616000066',  # PEP 2016
    '000104746916017244',  # DE 2016
]


def ctx(lines, center, before=5, after=10):
    lo = max(0, center - before)
    hi = min(len(lines), center + after + 1)
    for i in range(lo, hi):
        mark = '>>>' if i == center else '   '
        print(f'{mark} {i+1:5d}: {mod.norm(lines[i])}')


def summarize_candidates(lines, candidates):
    out = []
    for c in candidates:
        out.append({
            'line': c['line'],
            'start': c['start'],
            'score': round(c.get('score', 0), 1),
            'method': c['method'],
            'body': c.get('body_candidate'),
            'preview': c.get('preview', ''),
        })
    return out


def inspect(accession):
    df = pd.read_csv(mod.METADATA_PATH, dtype={'accession_number': str})
    target = mod.normalize_accession(accession)
    sub = df[df['accession_number'].map(mod.normalize_accession) == target]
    if sub.empty:
        raise RuntimeError(f'No filing matched {accession}')
    row = sub.iloc[0]
    path = mod.find_input_file(row)
    if path is None:
        raise RuntimeError(f'Processed file not found for {accession}')

    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    extracted, diagnostics = mod.extract_filing(lines)

    print('\n' + '=' * 100)
    print(f"{row['ticker']} | accession={target}")
    print(f'file={path}')
    print(f'lines={len(lines):,} words={mod.words(text):,}')
    print('=' * 100)

    for name in ['item_7_mda', 'item_7a_market_risk']:
        print(f'\n### {name}')
        chosen = extracted.get(name)
        if chosen is None:
            print('CHOSEN: NONE')
        else:
            c = chosen['candidate']
            end = chosen.get('end')
            print(
                f"CHOSEN: start_line={c['start']+1}, end_line={end}, "
                f"words={(0 if end is None else mod.words(' '.join(lines[c['start']:end])))} , "
                f"method={c['method']}, score={c.get('score',0):.1f}, "
                f"boundary={chosen.get('boundary_method')}"
            )
            print('PREVIEW:', mod.norm(lines[c['start']]))
            print('CONTEXT AROUND CHOSEN:')
            ctx(lines, c['start'])

        print('\nALL CANDIDATES (sorted by line):')
        for c in sorted(diagnostics.get(name, []), key=lambda x: x['start']):
            print(
                f"line={c['line']:5d} score={c.get('score',0):6.1f} "
                f"method={c['method']:24s} body={str(c.get('body_candidate')):5s} "
                f"preview={c.get('preview','')}"
            )

        if chosen and chosen.get('end') is not None:
            print('\nFIRST 15 NON-EMPTY LINES OF CHOSEN SECTION:')
            shown = 0
            for i in range(chosen['start'], chosen['end']):
                t = mod.norm(lines[i])
                if t:
                    print(f'  {i+1:5d}: {t}')
                    shown += 1
                    if shown >= 15:
                        break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--accession', action='append', help='Repeatable SEC accession')
    args = parser.parse_args()
    accessions = args.accession or DEFAULT_ACCESSIONS
    for acc in accessions:
        inspect(acc)


if __name__ == '__main__':
    main()
