"""The console pair, asserted on the two things it can silently get wrong.

`output.py` had no test file of its own until this one. Its renderers were
exercised only where a CLI test happened to run one, which covers the rendering
but none of the contract underneath it.

Two failures hide there. A colour map keyed on a verdict's string raises
`KeyError` at render time the day an enum gains a member, and that lands while a
run is already reporting something unusual. And the stdout/stderr split is a
machine contract rather than a preference — one diagnostic on stdout turns a
`--json` parse into a syntax error rather than the warning it actually was.

Neither is visible in a green suite otherwise, and both are cheap to assert.
"""

from __future__ import annotations

import json

import pytest

from dotfiles import output
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import ResourceVerdict
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Verdict


def a_change(**overrides) -> Change:
    """One stale package, which is the shape every renderer test starts from."""
    fields = {
        'resource': 'packages',
        'stage': Stage.ENVIRONMENT,
        'item': 'ripgrep',
        'verdict': Verdict.STALE,
        'detail': '14.1.0 to 14.1.1',
    }
    return Change(**(fields | overrides))


@pytest.mark.parametrize('verdict', list(ResourceVerdict))
def test_every_resource_verdict_has_a_colour(verdict: ResourceVerdict) -> None:
    """`render_result` indexes `VERDICT_COLOURS` on the verdict's string value,
    so a member added without an entry raises KeyError rather than rendering in a
    default colour."""
    assert str(verdict) in output.VERDICT_COLOURS


@pytest.mark.parametrize('verdict', list(Verdict))
def test_every_change_verdict_has_a_colour(verdict: Verdict) -> None:
    """Same failure as the resource map, one level down, and likelier: `Verdict`
    is the enum a new kind of item would extend."""
    assert str(verdict) in output.CHANGE_COLOURS


def test_emit_json_writes_a_document_and_nothing_else(capsys: pytest.CaptureFixture) -> None:
    output.emit_json({'machine': 'archlinux'})

    written = capsys.readouterr()
    assert json.loads(written.out) == {'machine': 'archlinux'}
    assert written.err == ''


def test_emit_json_does_not_wrap_a_long_value(capsys: pytest.CaptureFixture) -> None:
    """Rich wraps at the terminal width, which would put a newline inside a JSON
    string and hand the caller a different document from the one emitted. This is
    why `emit_json` uses `print`, and this test is what stops that being tidied
    back into `console.print`."""
    url = 'https://github.com/BurntSushi/ripgrep/releases/download/' + 'a' * 200

    output.emit_json({'url': url})

    assert url in capsys.readouterr().out


def test_emit_json_keeps_square_brackets(capsys: pytest.CaptureFixture) -> None:
    """Rich reads `[bold]` as markup and would drop it, so a detail string
    carrying brackets would parse back as different text."""
    output.emit_json({'detail': 'matched [bold] literally'})

    assert json.loads(capsys.readouterr().out)['detail'] == 'matched [bold] literally'


def test_emit_text_adds_nothing_of_its_own(capsys: pytest.CaptureFixture) -> None:
    """A wrapped `~/.env` line is a different file from the one that was asked
    for, and a trailing newline nobody wrote is a different file too."""
    body = 'MACHINE=archlinux\nDOTFILES_PKG=' + 'x' * 200 + '\n'

    output.emit_text(body)

    assert capsys.readouterr().out == body


def test_a_resource_row_is_the_answer_so_it_goes_to_stdout(capsys: pytest.CaptureFixture) -> None:
    """`render_result` is the non-`--json` rendering of what `check` and `plan`
    answer, so it belongs on the channel `--json` owns rather than beside it."""
    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 pending'))

    written = capsys.readouterr()
    assert 'packages' in written.out
    assert written.err == ''


def test_an_item_row_is_evidence_so_it_goes_to_stderr(capsys: pytest.CaptureFixture) -> None:
    """Below a composite `check` these are the evidence for the row that follows,
    not the answer a caller parses."""
    output.render_change(a_change())

    written = capsys.readouterr()
    assert 'ripgrep' in written.err
    assert written.out == ''


def test_advice_prints_on_its_own_line(capsys: pytest.CaptureFixture) -> None:
    """`detail` says what is wrong and `advice` says what to do about it. A
    reader scanning a screen of rows for the instruction wants it in one column,
    not folded into a sentence of varying length."""
    output.render_change(a_change(advice='run dotfiles apply'))

    lines = [line for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert len(lines) == 2
    assert 'run dotfiles apply' in lines[1]
    assert 'ripgrep' not in lines[1]


def test_the_observed_value_appears_only_when_there_is_one(capsys: pytest.CaptureFixture) -> None:
    """An empty `observed` renders as nothing rather than as `(is '')`, which
    would read as a measured empty string."""
    output.render_change(a_change(observed='14.1.0'))
    assert "is '14.1.0'" in capsys.readouterr().err

    output.render_change(a_change())
    assert '(is ' not in capsys.readouterr().err


def test_a_finding_shares_the_column_a_change_uses(capsys: pytest.CaptureFixture) -> None:
    """A finding is evidence for the `machines` row the way a Change is evidence
    for a resource's, so the two have to read as one list rather than two."""
    output.render_change(a_change())
    change_row = capsys.readouterr().err

    output.render_finding('go_tools', 'no such section')
    finding_row = capsys.readouterr().err

    assert change_row.index('ripgrep') == finding_row.index('go_tools')


def test_quiet_drops_the_evidence_and_keeps_the_verdict(capsys: pytest.CaptureFixture) -> None:
    """What `-q` actually buys. The rows are not log records, so before this the
    flag moved the log threshold and changed nothing a reader could see."""
    from dotfiles import logging

    logging.choose_console(quiet=True)

    output.render_change(a_change())
    output.render_finding('go_tools', 'no such section')
    output.heading('packages')
    assert capsys.readouterr().err == ''

    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 pending'))
    assert 'packages' in capsys.readouterr().out

    logging.choose_console()


def test_the_evidence_returns_when_the_flag_is_cleared(capsys: pytest.CaptureFixture) -> None:
    """Guards the test above: one that suppressed permanently would pass it and
    silence every later run in the same process."""
    output.render_change(a_change())

    assert 'ripgrep' in capsys.readouterr().err


@pytest.mark.parametrize('render', [output.heading, output.error, output.success, output.warn, output.hint])
def test_every_diagnostic_goes_to_stderr(render, capsys: pytest.CaptureFixture) -> None:
    """The whole reason there are two consoles. A diagnostic on stdout is
    indistinguishable from data to the caller parsing it."""
    render('something happened')

    written = capsys.readouterr()
    assert 'something happened' in written.err
    assert written.out == ''
