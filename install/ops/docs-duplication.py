#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Rank every page in `docs/` by how much of it is a second copy of a docstring.

The number is six-word runs a page shares with any docstring under `src/dotfiles/`
or `apps/`. A page carrying decisions scores in the single digits whatever its
length; a page walking through a mechanism the code already explains scores in
the hundreds. A page never restates a module docstring, and
`docs/development/docs-audit.md` § "Third pass" is the measurement this threshold
came from.

`--pages` points it at another directory of prose and `--code` is repeatable,
which is how the mutation harness's README is ranked against the package it sits
beside. A README beside its own code shares more vocabulary than a page in
`docs/` does, so `LOUD` is calibrated for the default set and reads high there.

Two limits, both deliberate. It compares prose against code and never prose
against prose, so it is blind to two pages stating one subject. And a high score
is a question rather than a verdict — shared vocabulary is not duplication, so
read the runs before cutting. `--runs` prints them.
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


DEFAULT_CODE = ('src/dotfiles', 'apps')
"""Both trees that carry docstrings a page could be restating.

`apps/` was outside this for as long as the tool existed, and `docs/apps/` is a
whole nav section — so the pages most likely to restate a docstring were the ones
it could not see. A script-app has no `.py` extension either, which is why the
walk below reads whatever is executable rather than globbing a suffix.
"""


def shingles(text: str, window: int = WINDOW) -> set[str]:
    words = re.findall(r'[a-z_`.\-/]+', text.lower())
    return {' '.join(words[index : index + window]) for index in range(max(0, len(words) - window))}


def source(root: Path, where: str) -> str:
    """Every readable source file under `where`, joined.

    `.py` plus anything executable, because `apps/` ships Python and bash under
    no extension at all. A binary that slips through is skipped rather than
    raising — the score is a ranking, and one unreadable file is not worth
    failing the run over.
    """
    collected = []
    for path in sorted((root / where).rglob('*')):
        if not path.is_file():
            continue
        if path.suffix != '.py' and not path.stat().st_mode & 0o111:
            continue
        try:
            collected.append(path.read_text())
        except (UnicodeDecodeError, OSError):
            continue
    return ' '.join(collected)


def named(page: Path, root: Path) -> Path:
    """The page as a reader would type it, repo-relative where it is in the repo.

    `--pages` takes any directory, and a ranking is unreadable if half of it is
    absolute — so the relative form is used where there is one and never assumed.
    """
    return page.relative_to(root) if page.is_relative_to(root) else page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', metavar='PAGE', help='print the shared runs for one page instead of the ranking')
    parser.add_argument('--max', type=int, default=LOUD, help=f'exit non-zero if any page scores above this (default {LOUD})')
    parser.add_argument('--pages', default='docs', help='directory of markdown to rank (default docs)')
    parser.add_argument(
        '--code',
        action='append',
        metavar='DIR',
        help='directory of code to compare against; repeatable (default src/dotfiles and apps)',
    )
    parsed = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    package = shingles(' '.join(source(root, where) for where in (parsed.code or DEFAULT_CODE)))

    if parsed.runs:
        page = Path(parsed.runs) if Path(parsed.runs).is_absolute() else root / parsed.runs
        for run in sorted(shingles(page.read_text()) & package):
            print(run)
        return 0

    scored = sorted(((len(shingles(page.read_text()) & package), page) for page in (root / parsed.pages).rglob('*.md')), reverse=True)
    for score, page in scored:
        print(f'{score:5d}  {named(page, root)}')
    print(f'\n{sum(score for score, _ in scored)} across {len(scored)} pages')

    loud = [named(page, root) for score, page in scored if score > parsed.max]
    if loud:
        print(f'\nabove {parsed.max}: {", ".join(str(page) for page in loud)}', file=sys.stderr)
        print('read the runs with --runs <page> before cutting', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
