#!/usr/bin/env python3
"""
Merge multiple Yellosa lead CSVs into one deduped file.

Usage:
  python3 merge_csv.py <output.csv> <input1.csv> [input2.csv ...]
  python3 merge_csv.py --dir <folder> --out <output.csv> [--glob "*.csv"]

Dedup key: company URL (unique per business) first, normalized name second.
The output file is excluded from its own inputs automatically.
"""
import csv
import os
import sys
import glob


def norm_key(row):
    url = (row.get('URL') or '').strip()
    name = (row.get('Name') or '').lower().replace('  ', ' ').strip()
    return (url, name) if url else (name,)


def main():
    args = sys.argv[1:]
    inputs = []
    out = None
    folder = None
    pattern = '*.csv'

    if args and args[0] == '--dir':
        i = args.index('--dir')
        folder = args[i + 1]
        if '--out' in args:
            out = args[args.index('--out') + 1]
        if '--glob' in args:
            pattern = args[args.index('--glob') + 1]
        inputs = sorted(glob.glob(os.path.join(folder, pattern)))
    else:
        # positional: first arg = output, rest = inputs
        out = args[0]
        inputs = args[1:]

    if not out or not inputs:
        print('Usage: merge_csv.py <output.csv> <in1.csv> [in2.csv ...]')
        print('   or: merge_csv.py --dir <folder> --out <output.csv> [--glob "*.csv"]')
        sys.exit(1)

    out = os.path.abspath(out)
    inputs = [os.path.abspath(p) for p in inputs if os.path.abspath(p) != out]
    # de-dup input list
    seen_paths = set()
    cleaned = []
    for p in inputs:
        if p not in seen_paths:
            seen_paths.add(p)
            cleaned.append(p)
    inputs = cleaned

    merged = []
    keys = set()
    header = None
    counts = {}
    for path in inputs:
        with open(path, newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            if header is None:
                header = reader.fieldnames
            rows = list(reader)
        counts[os.path.basename(path)] = len(rows)
        for r in rows:
            k = norm_key(r)
            if k in keys:
                continue
            keys.add(k)
            merged.append(r)

    if header is None:
        print('ERROR: no input files had a readable header; aborting.', file=sys.stderr)
        sys.exit(1)

    with open(out, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(merged)

    total_in = sum(counts.values())
    print('Inputs:')
    for name, n in counts.items():
        print(f'  {name}: {n}')
    print(f'Merged unique rows: {len(merged)} (from {total_in} input rows, {total_in - len(merged)} dup removed)')
    print(f'-> {out}')


if __name__ == '__main__':
    main()
