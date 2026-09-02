"""Which tests execute a line, measured rather than declared.

Only a test that executes the mutated line can kill the mutant, so that set is the exact subset to run — and it is already recorded by
`coverage --cov-context=test`. A hand-written module-to-tests map would be a second keying of the same fact, and it would rot from the first
renamed test onward.

**A line no test executes is answered without running anything.** An empty context set is UNREACHED, which is strictly worse than a
survivor and costs nothing to find: `report._send` had zero executed statements, so the whole function comes back in the time it
takes to read a JSON file.

**Import-time lines get the file's union.** A module constant runs while pytest is collecting, so coverage files it under the empty
context and no test name is attached. The union of every test that executes any line of that file is the honest answer — every one
of them imported the module, and a test that imported it without executing a line of it is the direction that over-reports survivors
rather than inventing kills.

The cache is keyed on a digest of the source and test trees and regenerated rather than repaired, because a stale context map is
indistinguishable from a correct one until it produces a wrong kill.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path

import coverage

IMPORT_TIME = ''
"""Coverage's name for "executed outside any test", which under pytest-cov means collection."""

PHASES = ('|run', '|setup', '|teardown')


@dataclasses.dataclass(frozen=True)
class Contexts:
    """Line-to-tests for every measured file, interned so the whole suite's map is a few megabytes rather than a few hundred.

    `lines` maps a repo-relative path to `{lineno: (index into `tests`, …)}`. A line present with an empty tuple ran at import time;
    a line absent was never executed at all, and the difference is the whole point of the structure.
    """

    tests: tuple[str, ...]
    lines: dict[str, dict[int, tuple[int, ...]]]

    def measured(self, relative: str) -> bool:
        return relative in self.lines

    def for_line(self, relative: str, lineno: int) -> tuple[str, ...]:
        """The tests that execute this line, falling back to the file's union for a line that only ran at import."""
        found = self.lines.get(relative, {}).get(lineno)
        if found is None:
            return ()
        if found:
            return tuple(self.tests[index] for index in found)
        return self.anywhere_in(relative)

    def anywhere_in(self, relative: str) -> tuple[str, ...]:
        indexes: set[int] = set()
        for found in self.lines.get(relative, {}).values():
            indexes.update(found)
        return tuple(self.tests[index] for index in sorted(indexes))

    def as_payload(self) -> dict:
        return {
            'tests': list(self.tests),
            'lines': {path: {str(line): list(found) for line, found in rows.items()} for path, rows in self.lines.items()},
        }

    @classmethod
    def from_payload(cls, payload: dict) -> Contexts:
        return cls(
            tests=tuple(payload['tests']),
            lines={path: {int(line): tuple(found) for line, found in rows.items()} for path, rows in payload['lines'].items()},
        )


def pythonpath(*roots: Path) -> str:
    """`PYTHONPATH` with the given roots in front of whatever the caller had.

    Order is the whole mechanism: a mutant worker puts its own copy first and the checkout's `src` second, so `import dotfiles`
    resolves to the copy and everything the copy does not shadow still resolves. `PYTHONPATH` precedes the editable install's `.pth`
    entry on `sys.path`, which is what makes the copy win without anything being written into the checkout.
    """
    return os.pathsep.join([*(str(root) for root in roots), os.environ.get('PYTHONPATH', '')]).rstrip(os.pathsep)


def strip_phase(context: str) -> str:
    """`tests/x.py::test_y|run` is one test measured in one phase; pytest is addressed by the part before the bar."""
    for phase in PHASES:
        if context.endswith(phase):
            return context[: -len(phase)]
    return context


def fingerprint(repo: Path, trees: Sequence[str] = ('src', 'tests')) -> str:
    """A digest of every `.py` under the named trees plus the pytest configuration.

    Content rather than mtime, so a checkout, a rebase and a stash all produce the same key when they produce the same files.
    """
    digest = hashlib.blake2b(digest_size=16)
    for tree in trees:
        for path in sorted((repo / tree).rglob('*.py')):
            digest.update(str(path.relative_to(repo)).encode())
            digest.update(path.read_bytes())
    pyproject = repo / 'pyproject.toml'
    if pyproject.is_file():
        digest.update(pyproject.read_bytes())
    return digest.hexdigest()


def read_data(basename: Path, repo: Path, source_root: Path) -> Contexts:
    """Turn a coverage data file into the interned map, keeping only files inside the repo."""
    data = coverage.CoverageData(str(basename))
    data.read()
    names: dict[str, int] = {}
    lines: dict[str, dict[int, tuple[int, ...]]] = {}
    for measured in data.measured_files():
        path = Path(measured)
        if not path.is_relative_to(source_root):
            continue
        relative = str(path.relative_to(repo))
        rows: dict[int, tuple[int, ...]] = {}
        for lineno, contexts in data.contexts_by_lineno(measured).items():
            found = sorted({strip_phase(context) for context in contexts} - {IMPORT_TIME})
            rows[lineno] = tuple(names.setdefault(name, len(names)) for name in found)
        lines[relative] = rows
    return Contexts(tests=tuple(sorted(names, key=lambda name: names[name])), lines=lines)


def measure(repo: Path, source_root: Path, *, pytest_prefix: Sequence[str], pytest_args: Sequence[str] = ()) -> Contexts:
    """One suite run with per-test contexts, into a data file nobody else is writing.

    `COVERAGE_FILE` points at a temporary directory rather than the repo, because the repo's own `.coverage` belongs to whatever a
    person last ran and this must not overwrite it.
    """
    with tempfile.TemporaryDirectory(prefix='dotfiles-mutation-contexts-') as scratch:
        basename = Path(scratch) / '.coverage'
        environment = dict(os.environ, COVERAGE_FILE=str(basename), PYTHONPATH=pythonpath(source_root))
        argv = [
            *pytest_prefix,
            '-q',
            '--no-header',
            '-p',
            'no:randomly',
            f'--cov={source_root}',
            '--cov-context=test',
            '--cov-report=',
            '--cov-fail-under=0',
            *pytest_args,
        ]
        completed = subprocess.run(argv, cwd=repo, env=environment, capture_output=True, text=True)
        if completed.returncode != 0:
            reason = f'the context pass exited {completed.returncode}; the suite has to be green before a mutant can be attributed'
            raise RuntimeError(f'{reason}\n{completed.stdout[-2000:]}')
        return read_data(basename, repo, source_root)


def load(
    repo: Path,
    source_root: Path,
    cache_dir: Path,
    *,
    pytest_prefix: Sequence[str],
    pytest_args: Sequence[str] = (),
    trees: Sequence[str] = ('src', 'tests'),
    refresh: bool = False,
) -> tuple[Contexts, Path, bool]:
    """The context map, from cache where the trees have not moved. Returns it with its cache path and whether it was measured now."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f'contexts-{fingerprint(repo, trees)}.json'
    if cached.is_file() and not refresh:
        # A run interrupted mid-write leaves a truncated map behind, and this one is written by a process a person may well
        # ctrl-C. Regenerate rather than repair, and refuse to read a half-file rather than reporting kills against a subset
        # that is missing rows.
        try:
            return Contexts.from_payload(json.loads(cached.read_text())), cached, False
        except (ValueError, KeyError, TypeError):
            cached.unlink(missing_ok=True)
    found = measure(repo, source_root, pytest_prefix=pytest_prefix, pytest_args=pytest_args)
    cached.write_text(json.dumps(found.as_payload()))
    _prune(cache_dir, keep=cached)
    return found, cached, True


def cache_for(root: Path, repo: Path) -> Path:
    """This checkout's own corner of the machine-global cache.

    Keyed on the repo path rather than on the fingerprint, because the
    fingerprint already varies per tree state and what has to be separated is
    the *checkout*: `git worktree list` reports eight here, and a sweep that
    cannot tell them apart evicts a peer's map.
    """
    return root / hashlib.blake2b(str(repo.resolve()).encode(), digest_size=6).hexdigest()


def _prune(cache_dir: Path, keep: Path, limit: int = 3) -> None:
    """Regenerate rather than repair, so old keys are dropped rather than accumulating a directory of maps nobody can date.

    **The directory is one checkout's, which is what makes the sweep per
    checkout.** `cache_for` puts each repo root under its own subdirectory, so
    three maps are kept *each* rather than three between every worktree — and a
    worktree is the normal way to work here. Each wrong eviction costs the next
    run a whole-suite pass under `--cov-context=test`. A cache holding several
    subjects is swept per subject.
    """
    found = sorted(cache_dir.glob('contexts-*.json'), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in [path for path in found if path != keep][limit:]:
        stale.unlink(missing_ok=True)


def union(subsets: Iterable[Iterable[str]]) -> tuple[str, ...]:
    found: set[str] = set()
    for subset in subsets:
        found.update(subset)
    return tuple(sorted(found))
