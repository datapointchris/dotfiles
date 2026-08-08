"""update.sh — which phases an argument list selects, and how a run reports.

What is under test in the first half is the selection, not what the phases do, so
these source update.sh and call `selected_phase_names` directly — the same
function `main` selects through. Going through `--dry-run` instead would resolve
every phase's item list, and each of those is a packages.yml parse; the one
dry-run test is deliberate and stands alone.

The second half is `report_snapshot_changes`, which exists because `uv tool
upgrade`, `cargo binstall` and `npm update -g` all exit 0 for a no-op: a success
line printed off an exit code could not tell an upgrade from nothing happening.
"""

from __future__ import annotations

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

UPDATE = str(REPO / 'update.sh')

GROUPS = ('system', 'languages', 'tools', 'plugins')

OWNER_AWARE = ('go-tools', 'cargo', 'uv-tools', 'github-releases', 'custom-installers')
"""What `--mine` keeps: the phases whose items carry a GitHub owner. npm resolves
against a registry rather than an owner, so it is not one of them."""


def select(*args: str) -> Shell:
    """Parse an argument list and print the phases it selects."""
    return shell_out(
        'source "$1"; shift; parse_args "$@"; selected_phase_names',
        UPDATE,
        *args,
        DOTFILES_DIR=str(REPO),
    )


def run_update(*args: str) -> Shell:
    return shell_out('bash "$@"', UPDATE, *args, DOTFILES_DIR=str(REPO))


def report(before: str, after: str, unchanged_message: str = 'already at latest') -> str:
    """Diff two snapshots the way a phase does around its upgrade."""
    result = shell_out(
        'source "$1"; report_snapshot_changes "$2" "$3" "$4"',
        UPDATE,
        before,
        after,
        unchanged_message,
        DOTFILES_DIR=str(REPO),
    )
    return result.stdout + result.stderr


def phases(result: Shell) -> set[str]:
    return set(result.stdout.split())


def test_no_arguments_selects_every_group() -> None:
    selected = phases(select())

    assert {'system-packages', 'go-toolchain', 'github-releases', 'nvim-plugins'} <= selected


@pytest.mark.parametrize(
    ('group', 'included', 'excluded'),
    [
        ('tools', 'github-releases', {'system-packages', 'nvim-plugins', 'go-toolchain'}),
        ('plugins', 'nvim-plugins', {'system-packages', 'github-releases'}),
        ('system', 'system-packages', {'github-releases', 'nvim-plugins'}),
    ],
)
def test_a_group_selects_its_own_phases_and_no_others(group: str, included: str, excluded: set[str]) -> None:
    selected = phases(select(group))

    assert included in selected
    assert not (excluded & selected)


def test_groups_combine() -> None:
    selected = phases(select('tools', 'plugins'))

    assert {'github-releases', 'nvim-plugins'} <= selected
    assert 'system-packages' not in selected


@pytest.mark.parametrize('skipped', [['--skip', 'plugins'], ['--skip', 'plugins', '--skip', 'system']])
def test_skip_removes_a_group_from_the_default_set(skipped: list[str]) -> None:
    selected = phases(select(*skipped))

    assert 'github-releases' in selected
    assert not ({'nvim-plugins', 'shell-plugins'} & selected)


def test_no_system_is_a_spelling_of_skip_system() -> None:
    """Two spellings of one thing must resolve identically, or the alias is a
    second implementation."""
    assert select('--no-system').stdout == select('--skip', 'system').stdout


def test_a_phase_name_selects_on_its_own_and_alongside_a_group() -> None:
    assert phases(select('go-tools')) == {'go-tools'}

    selected = phases(select('plugins', 'go-tools'))
    assert {'go-tools', 'nvim-plugins'} <= selected
    assert 'cargo' not in selected


def test_skip_takes_a_phase_name_as_well_as_a_group() -> None:
    selected = phases(select('tools', '--skip', 'cargo'))

    assert 'go-tools' in selected
    assert 'cargo' not in selected


@pytest.mark.parametrize('name', ['symlinks', 'config'])
def test_an_install_only_selection_is_refused(name: str) -> None:
    """symlinks runs at install time only, and config has no update phases at all,
    so naming either is a mistake rather than a no-op."""
    result = select(name)

    assert not result.ok


def test_mine_keeps_the_owner_aware_phases_and_nothing_else() -> None:
    selected = phases(select('--mine'))

    assert set(OWNER_AWARE) <= selected
    assert not ({'npm-globals', 'system-packages', 'shell-plugins', 'go-toolchain'} & selected)


def test_mine_intersected_with_a_group_owning_none_of_them_is_empty() -> None:
    result = select('--mine', 'plugins')

    assert result.ok
    assert result.stdout.strip() == ''


def test_list_names_every_group_and_says_which_support_mine() -> None:
    result = run_update('--list')

    assert result.ok
    assert all(group in result.stdout for group in GROUPS)
    assert 'supports --mine' in result.stdout


@pytest.mark.parametrize('flag', ['--no-system', '--mine'])
def test_help_documents_the_flags_that_are_not_groups(flag: str) -> None:
    """A flag with no group name to discover it by is only findable here."""
    result = run_update('--help')

    assert result.ok
    assert flag in result.stdout


@pytest.mark.parametrize(
    ('arguments', 'complaint'),
    [
        (['notagroup'], 'Unknown group'),
        (['--skip', 'bogus'], 'Unknown group'),
        (['--nonsense'], 'Unknown option'),
        (['--skip'], ''),
    ],
)
def test_every_shape_of_bad_argument_fails(arguments: list[str], complaint: str) -> None:
    result = select(*arguments)

    assert not result.ok
    assert complaint in result.stdout + result.stderr


def test_selecting_nothing_parses_cleanly_and_then_refuses_to_run() -> None:
    """Empty is a legitimate parse — it is the run that must not report success
    for having done nothing."""
    nothing = ['--skip', 'system', '--skip', 'languages', '--skip', 'tools', '--skip', 'plugins']

    parsed = select(*nothing)
    assert parsed.ok
    assert parsed.stdout.strip() == ''

    attempted = run_update('--dry-run', *nothing)
    assert not attempted.ok
    assert 'No phases selected' in attempted.stdout + attempted.stderr


def test_a_dry_run_resolves_every_phase_s_items_and_changes_nothing() -> None:
    """The one test that pays for package resolution, covering the `_items` hook
    of every owner-aware phase in a single invocation.

    The announcement is on stderr and the resolved items are on stdout, which is
    the split the whole output-streams rule exists for: the item list is what a
    caller would pipe, the narration is not.
    """
    result = run_update('--dry-run', '--mine')

    assert result.ok
    assert 'Dry run' in result.stderr
    assert 'theme' in result.stdout
    assert 'terraform-ls' not in result.stdout, '--mine must not reach a phase resolving against a registry'


def test_an_unchanged_snapshot_reports_the_no_op_message_and_no_movement() -> None:
    """The case that used to print a success line off an exit code."""
    snapshot = 'blink.cmp aaaaaaaaaaaa\ntelescope.nvim bbbbbbbbbbbb'

    rendered = report(snapshot, snapshot, 'Neovim plugins already at latest')

    assert 'Neovim plugins already at latest' in rendered
    assert 'updated' not in rendered


def test_a_changed_ref_reports_the_move_rather_than_the_no_op_message() -> None:
    rendered = report('blink.cmp aaaaaaaaaaaa', 'blink.cmp cccccccccccc')

    assert 'blink.cmp updated: aaaaaaaaaaaa → cccccccccccc' in rendered
    assert 'already at latest' not in rendered


def test_a_new_entry_reads_as_an_install_not_an_update() -> None:
    rendered = report('blink.cmp aaaaaaaaaaaa', 'blink.cmp aaaaaaaaaaaa\noil.nvim dddddddddddd')

    assert 'oil.nvim installed (dddddddddddd)' in rendered
    assert 'updated' not in rendered


def test_an_entry_that_disappeared_reads_as_a_removal() -> None:
    rendered = report('blink.cmp aaaaaaaaaaaa\noil.nvim dddddddddddd', 'blink.cmp aaaaaaaaaaaa')

    assert 'oil.nvim removed' in rendered


def test_an_empty_before_snapshot_is_a_first_install_not_an_update_of_everything() -> None:
    rendered = report('', 'blink.cmp aaaaaaaaaaaa')

    assert 'blink.cmp installed (aaaaaaaaaaaa)' in rendered
    assert 'removed' not in rendered
