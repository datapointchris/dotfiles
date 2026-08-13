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

import io
import json

import pytest
from rich.console import Console

from dotfiles import logging
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


def test_the_layer_that_supplied_a_value_is_named_only_when_there_is_one(capsys: pytest.CaptureFixture) -> None:
    """A registry absent at a path this machine's shells chose and one absent at a
    path its config file chose are different problems with one word for the
    outcome, so the value alone leaves the reader where they started.

    Asserted on the token rather than on its adjacency to `observed`, because the
    width that decides where the row wraps belongs to whoever ran the command.
    """
    output.render_change(a_change(observed='14.1.0', source='$REPOS_JSON'))
    assert '$REPOS_JSON' in capsys.readouterr().err

    output.render_change(a_change(observed='14.1.0'))
    assert 'from' not in capsys.readouterr().err


def test_a_source_with_no_observed_value_is_refused(capsys: pytest.CaptureFixture) -> None:
    """It renders as nothing, since the attribution rides inside the parenthesis
    `observed` opens — so the row would silently drop the half a reader came for."""
    with pytest.raises(ValueError, match='source with no observed value'):
        a_change(source='$REPOS_JSON')


@pytest.mark.parametrize('label', [*[str(verdict) for verdict in Verdict], 'invalid'])
def test_every_label_fits_the_column_it_is_padded_into(label: str) -> None:
    """A label wider than its column pushes the subject out of line for that row
    alone, which reads as a broken list rather than as a long word. `invalid` is
    here because `render_finding` writes it as a literal, so it is a label the
    enum does not cover.

    Asserted against the constant rather than by rendering two rows and comparing
    where they put a name: the alignment itself is now true by construction, since
    one constant feeds all three format strings.
    """
    assert len(label) <= output.VERDICT_COLUMN


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


def test_a_row_shows_the_counts_behind_its_verdict(capsys: pytest.CaptureFixture) -> None:
    """`ResourceResult` carried these four since it was written and no row ever
    showed them, so "converged" meant whatever the reader assumed."""
    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 differ', pending=4, privileged=2))

    written = capsys.readouterr().out
    assert '4 pending' in written
    assert '2 need a password' in written


def test_a_clean_row_shows_no_counts_at_all(capsys: pytest.CaptureFixture) -> None:
    """Four noughts on every line of a healthy machine is the pages of output this
    is trying not to become."""
    output.render_result(ResourceResult(address='symlinks', verdict=ResourceVerdict.CONVERGED, detail='all 172 deployed'))

    written = capsys.readouterr().out
    assert 'all 172 deployed' in written
    assert '·' not in written


def test_multi_line_advice_gets_one_row_per_line(capsys: pytest.CaptureFixture) -> None:
    """Advice is assembled from what a diagnosis measured — the owning package,
    then the command that removes it — and the command wants a line of its own."""
    output.render_change(a_change(advice='belongs to the pacman package shellcheck\nrun: sudo pacman -Rs shellcheck'))

    rows = [line for line in capsys.readouterr().err.splitlines() if '→' in line]
    assert len(rows) == 2
    assert 'sudo pacman -Rs shellcheck' in rows[1]


def test_an_issue_row_does_not_repeat_its_own_attention_count(capsys: pytest.CaptureFixture) -> None:
    """The verdict is made of those items and the detail already names them, so
    the count restated the sentence beside it."""
    output.render_result(
        ResourceResult(address='packages', verdict=ResourceVerdict.ISSUE, detail='4 item(s) need attention', attention=4, unmeasured=1)
    )

    written = capsys.readouterr().out
    assert '4 need attention' not in written
    assert '1 unmeasured' in written


def narrated(monkeypatch: pytest.MonkeyPatch, *, quiet: bool) -> str:
    """What the progress lines write, with a console that says it is a terminal.

    Forced, because `announce` has a second gate for whether anyone is watching
    and pytest's captured stderr is not a tty. Without this the quiet assertion
    passes on the wrong gate and would keep passing with `-q` ignored entirely.
    """
    written = io.StringIO()
    monkeypatch.setattr(output, 'err_console', Console(file=written, force_terminal=True, highlight=False))
    logging.choose_console(quiet=quiet)
    try:
        output.announce('packages', 'everything installed from a package manager')
        output.measured('packages', 'all 96 declared packages are installed', 1.0)
    finally:
        logging.choose_console()
    return written.getvalue()


def test_quiet_removes_the_progress_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """cli-design.md § "Quieten the evidence, never the answer" names the progress
    headings as exactly what `-q` removes. Ungated, `dotfiles apply -q` was louder
    after these lines were added than before them."""
    assert narrated(monkeypatch, quiet=True) == ''


def test_the_progress_line_is_there_without_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half, so the assertion above cannot pass by the lines never
    printing at all."""
    written = narrated(monkeypatch, quiet=False)

    assert 'packages' in written
    assert 'all 96 declared packages are installed' in written


def test_the_verdict_survives_quiet(capsys: pytest.CaptureFixture) -> None:
    """The answer keeps its channel whatever the flags say — a check reporting by
    exit code alone is a worse command rather than a quieter one."""
    logging.choose_console(quiet=True)
    try:
        output.render_result(ResourceResult('packages', ResourceVerdict.CONVERGED, 'all installed'))
    finally:
        logging.choose_console()

    assert 'all installed' in capsys.readouterr().out
