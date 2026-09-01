"""The two `install/ops/` sweeps, driven the way a hook drives them.

Both are gates now, so the exit code is the contract and a false positive costs
whoever is committing. Each sweep is handed a corpus built here rather than the
repo's own, because a gate measured against a tree that is green today says
nothing about what it rejects — `standards/testing.md` § "A guard is proved by
breaking what it names and watching it go red".

`negative()` decides four kinds of claim and each one carries findings, so each
gets a corpus that has to be reported. Deleting any single branch reddens a case
here.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from dotfiles import paths

OPS = paths.INSTALL_DIR / 'ops'

FINDING = re.compile(r'^\S+:\d+  (test_\w+)$', re.MULTILINE)
"""One reported test per line, which is what a count is read off rather than the summary sentence."""

RANKED = re.compile(r'^\s*(\d+)  (.+)$', re.MULTILINE)
"""One ranked page per line. Two spaces, which the `N across M pages` trailer does not have."""

CONFOUNDED = """
def test_it_writes_nothing():
    run(['tool', 'plan'])
    assert not (home / 'out.json').exists()
"""

ABSENT_FROM_A_STREAM = """
def test_it_says_nothing_about_the_declined_item():
    ran = run(['tool', 'plan'])
    assert 'zk' not in ran.stdout
"""

AN_EMPTY_STREAM = """
def test_a_refusal_never_reaches_stdout():
    result = run(['tool', 'land'])
    assert result.stdout == ''
"""

TWO_CLAIMS_IN_ONE_ASSERTION = """
def test_it_writes_neither():
    run(['tool', 'plan'])
    assert not (home / 'a.json').exists() and not (home / 'b.json').exists()
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


def reported(ran: subprocess.CompletedProcess[str]) -> list[str]:
    return FINDING.findall(ran.stdout)


def corpus(tmp_path: Path, body: str) -> Path:
    (tmp_path / 'test_subject.py').write_text(body)
    return tmp_path


class TestEveryKindOfNegativeClaimIsReported:
    """One case per branch of `negative()`. `not in` alone carried nine of the
    twenty-two findings this suite arrived with, so a branch losing its case is a
    gate that has quietly stopped covering most of what it found."""

    @pytest.mark.parametrize(
        ('body', 'name'),
        [
            pytest.param(CONFOUNDED, 'test_it_writes_nothing', id='not-x'),
            pytest.param(ABSENT_FROM_A_STREAM, 'test_it_says_nothing_about_the_declined_item', id='x-not-in-y'),
            pytest.param(AN_EMPTY_STREAM, 'test_a_refusal_never_reaches_stdout', id='x-equals-nothing'),
            pytest.param(TWO_CLAIMS_IN_ONE_ASSERTION, 'test_it_writes_neither', id='x-and-y'),
        ],
    )
    def test_the_shape_fails_the_gate(self, tmp_path: Path, body: str, name: str) -> None:
        ran = sweep(corpus(tmp_path, body))

        assert ran.returncode == 1
        assert reported(ran) == [name]


class TestWhatTheGateLetsThrough:
    def test_the_paired_exit_code_is_what_clears_it(self, tmp_path: Path) -> None:
        """The repair `standards/testing.md` prescribes, and the whole exemption."""
        ran = sweep(corpus(tmp_path, PAIRED))

        assert ran.returncode == 0
        assert reported(ran) == []

    def test_a_negative_claim_about_a_return_value_is_not_a_finding(self, tmp_path: Path) -> None:
        """A crash raises, so the empty string is only reachable by the code deciding on it."""
        ran = sweep(corpus(tmp_path, RETURN_VALUE))

        assert ran.returncode == 0
        assert reported(ran) == []

    def test_the_word_inside_a_string_literal_is_not_a_negative_claim(self, tmp_path: Path) -> None:
        """`assert 'not present' in ran.stdout` is a positive claim about stdout whose
        text carries the word. Matching the rendered line called three of those a
        finding, which is why the match reads the tree instead."""
        ran = sweep(corpus(tmp_path, POSITIVE_CLAIM_CARRYING_THE_WORD))

        assert ran.returncode == 0
        assert reported(ran) == []

    def test_a_docstring_naming_a_status_word_does_not_exempt_the_test(self, tmp_path: Path) -> None:
        """`raises` in prose exempted a test whose twin, twelve lines below, was reported."""
        ran = sweep(corpus(tmp_path, DOCSTRING_SAYING_RAISES))

        assert ran.returncode == 1
        assert reported(ran) == ['test_it_writes_nothing']

    def test_max_is_where_the_gate_sits_rather_than_whether_it_reports(self, tmp_path: Path) -> None:
        ran = sweep(corpus(tmp_path, CONFOUNDED), '--max', '1')

        assert ran.returncode == 0
        assert reported(ran) == ['test_it_writes_nothing'], 'raising the threshold hides nothing'


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

    def scores(self, ran: subprocess.CompletedProcess[str]) -> dict[str, int]:
        return {Path(page).name: int(score) for score, page in RANKED.findall(ran.stdout)}

    def test_a_page_restating_a_docstring_fails_the_gate(self, corpus: tuple[Path, Path]) -> None:
        pages, code = corpus
        (pages / 'page.md').write_text(PROSE)

        ran = self.rank(pages, code, '--max', '0')

        assert ran.returncode == 1
        assert self.scores(ran)['page.md'] > 0, 'it ranked the page rather than dying on it'
        assert 'page.md' in ran.stderr

    def test_a_page_sharing_no_prose_with_the_code_passes(self, corpus: tuple[Path, Path]) -> None:
        pages, code = corpus
        (pages / 'page.md').write_text('why the axes are chosen by hand instead of guessed at\n')

        ran = self.rank(pages, code, '--max', '0')

        assert ran.returncode == 0
        assert self.scores(ran) == {'page.md': 0}
        assert ran.stderr == ''
