"""The two `install/ops/` sweeps, driven the way a hook drives them.

Both are gates now, so the exit code is the contract and a false positive costs
whoever is committing. Each sweep is handed a corpus built here rather than the
repo's own, because a gate measured against a tree that is green today says
nothing about what it rejects — `standards/testing.md` § "A guard is proved by
breaking what it names and watching it go red".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / 'install' / 'ops'

CONFOUNDED = """
def test_it_writes_nothing():
    run(['tool', 'plan'])
    assert not (home / 'out.json').exists()
"""

PAIRED = """
def test_it_writes_nothing():
    ran = run(['tool', 'plan'])
    assert ran.returncode == 0
    assert not (home / 'out.json').exists()
"""

POSITIVE_CLAIM_CARRYING_THE_WORD = """
def test_it_says_the_file_is_absent():
    ran = cli('config', 'show')
    assert 'not present' in ran.stdout
"""

RETURN_VALUE = """
def test_it_answers_nothing_rather_than_raising():
    assert resolve(machine) == ''
    assert not (home / 'out.json').exists()
"""

DOCSTRING_SAYING_RAISES = '''
def test_it_writes_nothing():
    """A config that raises on startup is the failure this catches."""
    run(['tool', 'plan'])
    assert not (home / 'out.json').exists()
'''


def sweep(where: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OPS / 'undiscriminating-tests.py'), '--tests', str(where), *args],
        capture_output=True,
        text=True,
    )


def corpus(tmp_path: Path, body: str) -> Path:
    (tmp_path / 'test_subject.py').write_text(body)
    return tmp_path


class TestTheUndiscriminatingSweep:
    def test_the_shape_it_exists_to_catch_fails_the_gate(self, tmp_path: Path) -> None:
        ran = sweep(corpus(tmp_path, CONFOUNDED))

        assert ran.returncode == 1
        assert 'test_it_writes_nothing' in ran.stdout
        assert '1 tests assert only' in ran.stdout

    def test_the_paired_exit_code_is_what_clears_it(self, tmp_path: Path) -> None:
        """The repair `standards/testing.md` prescribes, and the whole exemption."""
        ran = sweep(corpus(tmp_path, PAIRED))

        assert ran.returncode == 0
        assert '0 tests assert only' in ran.stdout

    def test_a_negative_claim_about_a_return_value_is_not_a_finding(self, tmp_path: Path) -> None:
        """A crash raises, so the empty string is only reachable by the code deciding on it."""
        ran = sweep(corpus(tmp_path, RETURN_VALUE))

        assert ran.returncode == 0

    def test_the_word_inside_a_string_literal_is_not_a_negative_claim(self, tmp_path: Path) -> None:
        """`assert 'not present' in ran.stdout` is a positive claim about stderr whose
        text carries the word. Matching the rendered line called three of those a
        finding, which is why the match reads the tree instead."""
        ran = sweep(corpus(tmp_path, POSITIVE_CLAIM_CARRYING_THE_WORD))

        assert ran.returncode == 0
        assert 'test_it_says_the_file_is_absent' not in ran.stdout

    def test_a_docstring_naming_a_status_word_does_not_exempt_the_test(self, tmp_path: Path) -> None:
        """`raises` in prose exempted a test whose twin, six lines above, was reported."""
        ran = sweep(corpus(tmp_path, DOCSTRING_SAYING_RAISES))

        assert ran.returncode == 1
        assert 'test_it_writes_nothing' in ran.stdout

    def test_max_is_where_the_gate_sits_rather_than_whether_it_reports(self, tmp_path: Path) -> None:
        ran = sweep(corpus(tmp_path, CONFOUNDED), '--max', '1')

        assert ran.returncode == 0
        assert 'test_it_writes_nothing' in ran.stdout, 'raising the threshold hides nothing'


PROSE = 'the sweep walks every declared entry and reports the ones that did not land\n'


class TestTheDocsDuplicationSweep:
    """Its threshold is calibrated rather than chosen, so what is asserted here is
    that `--max` decides the exit code — never where the default sits."""

    @pytest.fixture
    def corpus(self, tmp_path: Path) -> tuple[Path, Path]:
        code, pages = tmp_path / 'code', tmp_path / 'pages'
        code.mkdir()
        pages.mkdir()
        (code / 'module.py').write_text(f'"""{PROSE}"""\n')
        return pages, code

    def rank(self, pages: Path, code: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(OPS / 'docs-duplication.py'), '--pages', str(pages), '--code', str(code), *args],
            capture_output=True,
            text=True,
        )

    def test_a_page_restating_a_docstring_fails_the_gate(self, corpus: tuple[Path, Path]) -> None:
        pages, code = corpus
        (pages / 'page.md').write_text(PROSE)

        ran = self.rank(pages, code, '--max', '0')

        ranked, total = ran.stdout.splitlines()[0], ran.stdout.splitlines()[-1]

        assert ran.returncode == 1
        assert 'page.md' in ranked and not total.startswith('0 '), 'it ranked the page rather than dying on it'
        assert 'above 0: ' in ran.stderr
        assert 'page.md' in ran.stderr

    def test_a_page_sharing_no_prose_with_the_code_passes(self, corpus: tuple[Path, Path]) -> None:
        pages, code = corpus
        (pages / 'page.md').write_text('why the axes are chosen by hand instead of guessed at\n')

        ran = self.rank(pages, code, '--max', '0')

        assert ran.returncode == 0
        assert ran.stderr == ''
