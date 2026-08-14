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

import functools
import io
import json

import pytest
from rich.console import Console

from dotfiles import logging
from dotfiles import output
from dotfiles.reconcile import Lens
from dotfiles.reconcile import ResourceResult
from dotfiles.reconcile import ResourceVerdict
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


def a_change(**overrides) -> Change:
    """One stale package, which is the shape every renderer test starts from."""
    fields = {
        'resource': 'packages',
        'stage': Stage.ENVIRONMENT,
        'item': 'ripgrep',
        'verdict': Verdict.STALE,
        'repair': Repair.AUTOMATIC,
        'detail': '14.1.0 to 14.1.1',
    }
    return Change(**(fields | overrides))  # type: ignore[arg-type]


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
    body = 'MACHINE=archlinux\nOPENAI_API_KEY=' + 'x' * 200 + '\n'

    output.emit_text(body)

    assert capsys.readouterr().out == body


def test_a_resource_row_is_the_answer_so_it_goes_to_stdout(capsys: pytest.CaptureFixture) -> None:
    """`render_result` is the non-`--json` rendering of what `check` and `plan`
    answer, so it belongs on the channel `--json` owns rather than beside it."""
    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 pending'), output.console)

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


def test_a_backslash_in_an_observed_value_is_printed_once(capsys: pytest.CaptureFixture) -> None:
    """`repr` doubles it, and a credential helper is a shell command line where the
    count is the whole question. A path escaped once, shown as escaped twice, is
    unreadable exactly when someone is reading it to count them."""
    output.render_change(a_change(observed=r'/mnt/c/Program\ Files/Git/gcm.exe'))

    assert r"'/mnt/c/Program\ Files/Git/gcm.exe'" in capsys.readouterr().err


def test_a_control_character_still_renders_escaped() -> None:
    """A raw newline would break one row into two and put the second half under a
    column that means something else."""
    assert output.quoted('one\ntwo') == "'one\\ntwo'"


def test_a_value_keeps_its_quotes_so_a_trailing_space_stays_visible() -> None:
    assert output.quoted('delta ') == "'delta '"


def test_the_layer_that_supplied_a_value_is_named_only_when_there_is_one(capsys: pytest.CaptureFixture) -> None:
    """A registry absent at a path this machine's shells chose and one absent at a
    path its config file chose are different problems with one word for the
    outcome, so the value alone leaves the reader where they started.

    Asserted on the token rather than on its adjacency to `observed`, because the
    width that decides where the row wraps belongs to whoever ran the command.
    """
    output.render_change(a_change(observed='14.1.0', source='$DOTFILES_REPOS_REGISTRY'))
    assert '$DOTFILES_REPOS_REGISTRY' in capsys.readouterr().err

    output.render_change(a_change(observed='14.1.0'))
    assert 'from' not in capsys.readouterr().err


def test_a_source_with_no_observed_value_is_refused(capsys: pytest.CaptureFixture) -> None:
    """It renders as nothing, since the attribution rides inside the parenthesis
    `observed` opens — so the row would silently drop the half a reader came for."""
    with pytest.raises(ValueError, match='source with no observed value'):
        a_change(source='$DOTFILES_REPOS_REGISTRY')


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
    output.render_section('packages', 'everything installed from a package manager')
    assert capsys.readouterr().err == ''

    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 pending'), output.console)
    assert 'packages' in capsys.readouterr().out

    logging.choose_console()


def test_the_evidence_returns_when_the_flag_is_cleared(capsys: pytest.CaptureFixture) -> None:
    """Guards the test above: one that suppressed permanently would pass it and
    silence every later run in the same process."""
    output.render_change(a_change())

    assert 'ripgrep' in capsys.readouterr().err


@pytest.mark.parametrize(
    'render',
    [functools.partial(output.render_section, 'packages'), output.error, output.success, output.warn, output.hint],
    ids=['section', 'error', 'success', 'warn', 'hint'],
)
def test_every_diagnostic_goes_to_stderr(render, capsys: pytest.CaptureFixture) -> None:
    """The whole reason there are two consoles. A diagnostic on stdout is
    indistinguishable from data to the caller parsing it.

    `render_section` is in the list because an `apply`'s whole human report goes to
    this stream, its closing line included — so every line that verb prints is on
    the side its `--json` document is not."""
    render('something happened')

    written = capsys.readouterr()
    assert 'something happened' in written.err
    assert written.out == ''


def test_a_row_shows_the_counts_behind_its_verdict(capsys: pytest.CaptureFixture) -> None:
    """`ResourceResult` carried these since it was written and no row ever showed
    them, so "converged" meant whatever the reader assumed."""
    output.render_result(
        ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 differ', pending=4, privileged=2), output.console
    )

    written = capsys.readouterr().out
    assert '2 need a password' in written


def test_a_plan_row_words_the_other_half_as_the_other_verb_owns_it(capsys: pytest.CaptureFixture) -> None:
    """The row Chris read as self-contradictory: `plan` said `converged` and the
    tally beside it said `4 need attention`. Both were true — apply has nothing to
    do, and four CLIs are logged out — and the pair read as one row disagreeing
    with itself."""
    result = ResourceResult(address='auth', verdict=ResourceVerdict.CONVERGED, detail='3 of 7 authenticated', lens=Lens.PLAN, attention=4)

    output.render_result(result, output.console)

    written = capsys.readouterr().out
    assert '4 need a person' in written
    assert 'attention' not in written


def test_a_check_row_calls_pending_drift_what_it_is(capsys: pytest.CaptureFixture) -> None:
    """The mirror case, and the pairing worth keeping: nothing is wrong, and three
    declared packages are merely absent. `pending` is `plan`'s word for its own
    answer, so on this side it is named as the difference it is."""
    result = ResourceResult(address='packages', verdict=ResourceVerdict.CONVERGED, detail='all installed', lens=Lens.CHECK, pending=3)

    output.render_result(result, output.console)

    assert '3 differ' in capsys.readouterr().out


def test_a_verb_never_restates_its_own_answer_as_a_tally(capsys: pytest.CaptureFixture) -> None:
    """A `check` issue row is *made of* the items needing a person and its detail
    names them, and a `plan` drift row is made of what it would change. Either
    count beside its own sentence is the sentence twice."""
    output.render_result(
        ResourceResult(address='auth', verdict=ResourceVerdict.ISSUE, detail='4 item(s) need a person', lens=Lens.CHECK, attention=4),
        output.console,
    )
    assert '·' not in capsys.readouterr().out

    output.render_result(
        ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail='4 item(s) differ', lens=Lens.PLAN, pending=4),
        output.console,
    )
    assert '·' not in capsys.readouterr().out


def test_a_clean_row_shows_no_counts_at_all(capsys: pytest.CaptureFixture) -> None:
    """Four noughts on every line of a healthy machine is the pages of output this
    is trying not to become."""
    output.render_result(ResourceResult(address='symlinks', verdict=ResourceVerdict.CONVERGED, detail='all 172 deployed'), output.console)

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


def test_an_unmeasurable_count_survives_the_wording_rules(capsys: pytest.CaptureFixture) -> None:
    """It is neither verb's answer, so neither suppresses it. It is also the one
    count whose word is the same on both sides."""
    output.render_result(
        ResourceResult(
            address='packages', verdict=ResourceVerdict.ISSUE, detail='4 item(s) need a person', lens=Lens.CHECK, attention=4, unmeasured=1
        ),
        output.console,
    )

    assert '1 unmeasured' in capsys.readouterr().out


def test_the_evidence_is_printed_under_the_verdict_it_belongs_to(capsys: pytest.CaptureFixture) -> None:
    """The defect Chris hit. Rendered while folding, `auth`'s four logged-out rows
    landed above every resource's verdict, directly under the progress line for
    `credentials` — which then reported converged two lines below them.

    Both streams are read, because the pair only reads as one section on a
    terminal where they interleave."""
    finding = a_change(resource='auth', item='nomad', verdict=Verdict.MISSING, detail='the OS keychain holds no token')
    result = ResourceResult(
        address='auth', verdict=ResourceVerdict.ISSUE, detail='1 item(s) need a person', lens=Lens.CHECK, findings=(finding,)
    )

    output.render_result(result, output.console)

    written = capsys.readouterr()
    assert 'auth' in written.out
    assert 'nomad' in written.err


def test_a_small_resource_names_its_items_rather_than_counting_them(capsys: pytest.CaptureFixture) -> None:
    """ "go, node, rust, uv" is a list crammed into prose, and it drops the version
    of each — which is the one fact anybody opens that row for."""
    result = ResourceResult(
        address='toolchains',
        verdict=ResourceVerdict.CONVERGED,
        detail='go, node, rust, uv',
        examined=(Examined('toolchain/go', '1.25.0'), Examined('toolchain/uv', '0.9.2')),
    )

    output.render_result(result, output.console)

    written = capsys.readouterr().err
    assert 'toolchain/go' in written
    assert '1.25.0' in written


def test_a_large_resource_keeps_its_count_until_verbose_asks(capsys: pytest.CaptureFixture) -> None:
    """Above the threshold the summary is a genuine collapse rather than a list in
    disguise, and `-v` is the flag that expands it — cli-design.md § "`-a` is not a
    substitute for `-v`", since the work is identical either way."""
    result = ResourceResult(
        address='symlinks',
        verdict=ResourceVerdict.CONVERGED,
        detail='all 173 declared symlinks are deployed',
        examined=tuple(Examined(f'configs/file{index}', '~/.config') for index in range(output.LISTED_MAX + 1)),
    )

    output.render_result(result, output.console)
    assert capsys.readouterr().err == ''

    logging.choose_console(verbose=1)
    try:
        output.render_result(result, output.console)
    finally:
        logging.choose_console()

    assert 'configs/file7' in capsys.readouterr().err


def test_the_label_on_a_listed_item_is_the_verdict_a_change_would_carry(capsys: pytest.CaptureFixture) -> None:
    """`MATCHED` spelled as a literal in `output`, so presentation is not a reason
    to import the logic. This is what stops the two drifting apart."""
    assert str(Verdict.MATCHED) == output.MATCHED

    output.render_examined(Examined('toolchain/go', '1.25.0'))

    assert output.MATCHED in capsys.readouterr().err


def test_retracting_without_a_progress_line_to_take_back_writes_nothing(capsys: pytest.CaptureFixture) -> None:
    """It erases the line above it, so a run where `announce` printed nothing would
    eat whatever was there instead. Both are gated on the same two questions."""
    output.retract()

    assert capsys.readouterr().err == ''


def test_the_progress_line_is_taken_back_when_its_answer_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    """A progress line is a statement in the present tense. Left on screen, nine of
    them carrying nine resource descriptions read as a second report, and the
    reader's question becomes which of the two lists is the answer."""
    written = io.StringIO()
    monkeypatch.setattr(output, 'err_console', Console(file=written, force_terminal=True, highlight=False))

    output.announce('packages', 'everything installed from a package manager')
    output.retract()

    assert '\x1b[1A' in written.getvalue()


def test_the_progress_line_survives_verbose_because_the_log_lands_under_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """It erases the line above, not the announcement by identity. At `-v` the
    engine logs `measured` and every `effects.run` logs `ran` to this same console
    in between, so the row above the answer is a log line rather than the
    progress line."""
    written = io.StringIO()
    monkeypatch.setattr(output, 'err_console', Console(file=written, force_terminal=True, highlight=False))
    logging.choose_console(verbose=1)
    try:
        output.announce('packages', 'everything installed from a package manager')
        output.retract()
    finally:
        logging.choose_console()

    assert '\x1b[1A' not in written.getvalue()


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
        output.render_section('packages', 'all 96 declared packages are installed', 1.0)
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
        output.render_result(ResourceResult('packages', ResourceVerdict.CONVERGED, 'all installed'), output.console)
    finally:
        logging.choose_console()

    assert 'all installed' in capsys.readouterr().out


def test_the_section_heading_is_the_resource_name_not_its_verdict(capsys: pytest.CaptureFixture) -> None:
    """Spelled out on every section, `converged` was the word nine deep down the
    one column a reader scans for the name of the thing. The verdict is a mark
    here and the word appears once, on the closing line."""
    output.render_result(ResourceResult(address='packages', verdict=ResourceVerdict.CONVERGED, detail='all 96 installed'), output.console)

    written = capsys.readouterr().out
    assert 'converged' not in written
    assert written.startswith(f'{output.VERDICT_MARKS["converged"]} packages')


def test_every_resource_verdict_has_a_mark_as_well_as_a_colour() -> None:
    """`NO_COLOR` is a preference this fleet honours, so a report carrying its
    verdict only in an escape code answers nothing on a machine that asked for
    none."""
    assert set(output.VERDICT_MARKS) == set(output.VERDICT_COLOURS)


def test_a_section_ends_with_a_blank_line(capsys: pytest.CaptureFixture) -> None:
    """Nine sections run together read as one list of rows rather than as nine
    answers. After rather than before, so the closing line sits below a gap too and
    nothing has to remember whether it is first."""
    output.render_result(ResourceResult(address='symlinks', verdict=ResourceVerdict.CONVERGED, detail='all 173 deployed'), output.console)

    assert capsys.readouterr().out.endswith('\n\n')


def test_a_summary_with_two_sentences_aligns_the_second_and_carries_the_counts(capsys: pytest.CaptureFixture) -> None:
    """`system` measures a hundred packages and nine configuration rows, and joined
    by a comma they made the longest row in the report. The counts ride on the last
    line, because a tally wedged between two halves of a sentence separates them."""
    result = ResourceResult(
        address='system',
        verdict=ResourceVerdict.CONVERGED,
        detail='all 100 declared system packages installed\n9 configuration item(s) match',
        lens=Lens.CHECK,
        unmeasured=1,
    )

    output.render_result(result, output.console)

    first, second, *_ = capsys.readouterr().out.splitlines()
    assert '·' not in first
    assert second.strip().startswith('9 configuration item(s) match')
    assert '1 unmeasured' in second


def test_a_group_small_enough_to_read_lists_while_its_neighbour_stays_a_count(capsys: pytest.CaptureFixture) -> None:
    """One threshold over the whole resource could only suppress both, and the nine
    `system.yml` rows are worth naming on every run where a hundred packages are
    not."""
    result = ResourceResult(
        address='system',
        verdict=ResourceVerdict.CONVERGED,
        detail='all installed',
        examined=(
            *(Examined(f'pacman/pkg{index}', 'installed', group='system') for index in range(output.LISTED_MAX + 1)),
            Examined('group/docker', 'Docker socket access without sudo', group='configuration'),
        ),
    )

    output.render_result(result, output.console)

    written = capsys.readouterr().err
    assert 'group/docker' in written
    assert 'pacman/pkg0' not in written


def test_a_section_widens_its_subject_column_to_the_longest_item_in_it(capsys: pytest.CaptureFixture) -> None:
    """An alignment that holds for most rows and breaks for a few reads as a broken
    table rather than as a wide word."""
    rows = (Examined('shell-plugin/zsh-syntax-highlighting', 'cloned'), Examined('tpm/tpm', 'cloned'))
    result = ResourceResult(address='plugins', verdict=ResourceVerdict.CONVERGED, detail='all present', examined=rows)

    output.render_result(result, output.console)

    long, short = (line for line in capsys.readouterr().err.splitlines() if 'cloned' in line)
    assert long.index('cloned') == short.index('cloned')


def test_the_subject_column_stops_widening_for_one_very_long_item(capsys: pytest.CaptureFixture) -> None:
    """Past the ceiling the column costs every other row more than the long one
    gains, and the detail is pushed off a narrow terminal entirely."""
    rows = (Examined('a' * 200, 'here'), Examined('tpm/tpm', 'here'))
    result = ResourceResult(address='plugins', verdict=ResourceVerdict.CONVERGED, detail='all present', examined=rows)

    output.render_result(result, output.console)

    short = next(line for line in capsys.readouterr().err.splitlines() if line.strip().startswith('matched') and 'tpm' in line)
    columns = (output.EVIDENCE_INDENT, ' ' * output.VERDICT_COLUMN, ' ', ' ' * output.SUBJECT_CEILING, ' ')
    assert short.index('here') == len(''.join(columns))
