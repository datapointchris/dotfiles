#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Rank every page in `docs/` by how much of it is a second copy of a docstring.

The number is six-word runs a page shares with any docstring under
`src/dotfiles/`. A page carrying decisions scores in the single digits whatever
its length; a page walking through a mechanism the code already explains scores
in the hundreds. `standards/documentation.md` § "A page never restates a module
docstring" is the rule, and `docs/development/docs-audit.md` § "Third pass" is
the measurement this threshold came from.

Two limits, both deliberate. It compares against `src/dotfiles/` only, so it is
blind to two pages stating one subject. And a high score is a question rather
than a verdict — shared vocabulary is not duplication, so read the runs before
cutting. `--runs` prints them.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WINDOW = 6
LOUD = 100
"""Where a score stops being vocabulary and starts being copied prose.

Calibrated rather than chosen: the pages two earlier audits named as healthy
scored 0 and 1, and the four that had been rewritten every other commit scored
between 529 and 613. Nothing in the corpus has ever sat near this line.
"""


def shingles(text: str, window: int = WINDOW) -> set[str]:
    words = re.findall(r'[a-z_`.\-/]+', text.lower())
    return {' '.join(words[index : index + window]) for index in range(max(0, len(words) - window))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', metavar='PAGE', help='print the shared runs for one page instead of the ranking')
    parser.add_argument('--max', type=int, default=LOUD, help=f'exit non-zero if any page scores above this (default {LOUD})')
    parsed = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    package = shingles(' '.join(path.read_text() for path in (root / 'src' / 'dotfiles').rglob('*.py')))

    if parsed.runs:
        page = Path(parsed.runs) if Path(parsed.runs).is_absolute() else root / parsed.runs
        for run in sorted(shingles(page.read_text()) & package):
            print(run)
        return 0

    scored = sorted(((len(shingles(page.read_text()) & package), page) for page in (root / 'docs').rglob('*.md')), reverse=True)
    for score, page in scored:
        print(f'{score:5d}  {page.relative_to(root)}')
    print(f'\n{sum(score for score, _ in scored)} across {len(scored)} pages')

    loud = [page.relative_to(root) for score, page in scored if score > parsed.max]
    if loud:
        print(f'\nabove {parsed.max}: {", ".join(str(page) for page in loud)}', file=sys.stderr)
        print('read the runs with --runs <page> before cutting', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
