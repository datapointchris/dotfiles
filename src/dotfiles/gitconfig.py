"""What git actually reads on this machine, and where each setting came from.

The configuration reaches git through a chain of includes rather than a file:
the entry point includes the repo's shared config, that includes one file per
coordinate axis, and a trust overlay includes the identity — conditionally, on a
machine that keeps more than one. Every hop is deliberate and none of it is
visible. `git config --list --show-origin` prints the leaves with no indication
of how any of them was reached, and a key set in two files appears as two rows
that look like a repetition rather than an override.

**The chain is read out of the configuration itself, never assembled here.** An
`include.path` is a setting like any other, so the listing already carries which
file named which — a second description of the layering, kept in this module by
hand, is one that would disagree with the deployment the first time an overlay
moved. That is also what makes this correct on a machine whose layers this repo
has never seen.

**A repeated key is not by itself a finding**, and this is the whole difficulty.
Git's own idiom for replacing an inherited credential helper is to set the key
empty and then set it again, so `common.gitconfig` legitimately lists
`credential.https://github.com.helper` twice — and a detector that called that
drift would be wrong on a healthy machine, on every run, which is how a detector
comes to be ignored. What is reported is narrower and is always a real ambiguity:
one key given *different* values by two *different* files, where the reader has
no way to tell which one won.
"""

from __future__ import annotations

import dataclasses as dc
import fnmatch
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import quoted


def entry_point(home: Path | None = None) -> Path:
    """Where git reads a global config from, under XDG, and where it writes one.

    Only while `~/.gitconfig` is absent. That is the whole of why the file below
    matters: git prefers the home-directory spelling for reads *and* writes, so
    one sitting there silently outranks this entire chain.

    Takes a home rather than reading one, so a caller holding a `Session` passes
    the home that session is about. `deploy.py` reaches these paths as module
    constants and has to be monkeypatched to be tested at all, which is the seam
    this avoids inheriting.
    """
    return (home or Path.home()) / '.config' / 'git' / 'config'


def home_config(home: Path | None = None) -> Path:
    return (home or Path.home()) / '.gitconfig'


@dc.dataclass(frozen=True, slots=True)
class Setting:
    """One key, its value, and the file git took it from."""

    origin: Path
    key: str
    value: str


INCLUDE_KEY = 'include.path'
CONDITIONAL_PREFIX = 'includeif.'
"""How git spells the two kinds of include in a listing.

A conditional one arrives as `includeif.<condition>.path`, and it is listed
whether or not its condition held — the key is in the file either way. Only the
settings that follow say whether it was taken, which is what `Include.taken`
reads and why a condition cannot be believed from its presence.
"""


def _is_include(key: str) -> bool:
    return key == INCLUDE_KEY or (key.startswith(CONDITIONAL_PREFIX) and key.endswith('.path'))


ACCUMULATING = (
    'credential.helper',
    'credential.*.helper',
    'http.extraheader',
    'http.*.extraheader',
    'url.*.insteadof',
    'url.*.pushinsteadof',
    'remote.*.fetch',
    'remote.*.push',
    'push.pushoption',
    'safe.directory',
)
"""Keys git collects rather than resolves, as `fnmatch` patterns.

**A second value for one of these is not a second opinion.** Git keeps them all
and uses them all, so two files each naming a credential helper produce two
helpers — tried in the order the files were read, and the first that answers
supplies the credential. Measured against git 2.55 with a silent helper and an
answering one configured in that order: both were executed, and the answer came
from the second.

Reading that as an override is wrong twice over. It names a winner that never
won anything, and the advice it carries is to consolidate into one file, which
on this key means deleting a helper that works. The credential resource had it
right already and lists every helper separately; this detector was the one
calling a healthy stack a conflict.

Matched against the key lowercased, because a listing lowercases the section and
the key and leaves a subsection's case alone — `credential.https://GitHub.com.helper`.
"""


def _accumulates(key: str) -> bool:
    return any(fnmatch.fnmatchcase(key.lower(), pattern) for pattern in ACCUMULATING)


@dc.dataclass(frozen=True, slots=True)
class Include:
    """One file pulling in another, and whether it actually did."""

    source: Path
    target: Path
    condition: str = ''
    """What has to hold for this include to be taken, or '' when it always is."""

    taken: bool = True
    """Whether the target contributed any setting to this machine.

    Measured rather than assumed. A conditional include appears in the listing
    with its condition unevaluated, so a nonfleet machine lists the personal
    identity's include from inside every directory and takes it in almost none of
    them — and a chain drawn from the keys alone would show an identity that is
    not being used.
    """


@dc.dataclass(frozen=True, slots=True)
class Conflict:
    """One key two files disagree about.

    Both files are named because the finding is the *pair*: either alone is a
    legitimate setting, and what a reader cannot see is that the second one is
    silently deciding.

    **One setting per file, never one per occurrence.** Git resolves a key set
    twice inside one file to that file's last word, so a file has exactly one
    answer however many times it says it — and this carried the occurrences.
    `core.pager` set twice in the entry point and once in a leaf read as `set in
    3 files` across two, and named the entry point twice in the advice. Holding
    the collapsed list rather than counting around it makes the wrong shape
    unrepresentable instead of leaving every reader to remember the difference.
    """

    key: str
    settings: tuple[Setting, ...]
    """Each file's last word on this key, in the order git read them."""

    @property
    def winner(self) -> Setting:
        """The one git resolves to, which is the last file to set it."""
        return self.settings[-1]

    @property
    def losers(self) -> tuple[Setting, ...]:
        return self.settings[:-1]

    @property
    def files(self) -> int:
        return len(self.settings)


@dc.dataclass(frozen=True, slots=True)
class Layering:
    """Everything this machine's git configuration is made of."""

    settings: tuple[Setting, ...]
    read: bool = True
    """Whether git answered at all. False leaves every finding below empty rather
    than reporting a machine with no configuration, which is what a git that could
    not be run would otherwise look like."""

    @property
    def files(self) -> tuple[Path, ...]:
        """Every file that contributed a setting, in the order git read them."""
        seen: dict[Path, None] = {}
        for setting in self.settings:
            seen.setdefault(setting.origin)
        return tuple(seen)

    @property
    def includes(self) -> tuple[Include, ...]:
        """Which file pulled in which, read off the include settings themselves."""
        contributed = {setting.origin for setting in self.settings}
        found = []
        for setting in self.settings:
            if not _is_include(setting.key):
                continue
            target = _resolved(setting.value, setting.origin)
            condition = setting.key.removeprefix(CONDITIONAL_PREFIX).removesuffix('.path') if setting.key != INCLUDE_KEY else ''
            found.append(Include(setting.origin, target, condition, taken=target in contributed))
        return tuple(found)

    @property
    def conflicts(self) -> tuple[Conflict, ...]:
        """Keys more than one file sets, to more than one value.

        Grouped by key and then narrowed three times, and every narrowing is what
        keeps this quiet on a healthy machine. A key repeated inside one file is
        git's multi-value idiom. A key several files agree on is not an ambiguity —
        the reader gets the value they would have predicted whichever file they
        read.

        And an include is excluded outright, because it is not a setting whose
        value gets resolved: every include in the chain is spelled `include.path`,
        so treating them as one key made the entire layering read as one enormous
        conflict with itself. That was this detector's first output on a machine
        with nothing wrong with it, which is precisely how a detector earns being
        ignored.

        An `ACCUMULATING` key is excluded for the same reason one layer down. Git
        resolves nothing there either — it runs every value — so a second one is
        an addition and not an override, and the winner this would name does not
        exist.
        """
        by_key: dict[str, list[Setting]] = {}
        for setting in self.settings:
            if not _is_include(setting.key) and not _accumulates(setting.key):
                by_key.setdefault(setting.key, []).append(setting)

        found = []
        for key, settings in by_key.items():
            # Collapsed to each file's last word before anything is compared. A
            # dict keyed on the origin keeps the final occurrence and, because it
            # preserves insertion order, keeps the order git read the files in —
            # so the last entry is still the value in effect.
            per_file = {setting.origin: setting for setting in settings}
            decided = tuple(per_file.values())
            if len(decided) < 2 or len({setting.value for setting in decided}) < 2:
                continue
            found.append(Conflict(key, decided))
        return tuple(found)


def _resolved(value: str, origin: Path) -> Path:
    """An include path as git resolves it: `~` at home, relative to its includer."""
    named = Path(value).expanduser()
    return named if named.is_absolute() else (origin.parent / named)


def read(scope: str = '--global') -> Layering:
    """Ask git what it reads, includes resolved.

    `--global` by default, because the question this exists for is what *this
    machine* is configured with — a repo-local override is a different question
    and `resources/identity.py` already asks it separately.

    A git that will not answer produces an empty layering rather than an
    exception. Nothing here is worth failing a whole check for: the caller is
    reporting on configuration, and "git could not be run" is a finding its own
    resource already makes.
    """
    result = run(['git', 'config', scope, '--list', '--show-origin', '--includes', '-z'], output=Output.QUIET)
    if not result.ok:
        return Layering((), read=False)
    return Layering(tuple(_parse(result.stdout)))


def document(layering: Layering, masked_by: Path | None) -> dict:
    """The layering as a caller parses it, matching what `render` draws.

    Built from the same three properties the tree is, so the two cannot come to
    different conclusions about which file won or whether an include fired. What
    a reader wants from this is exactly what makes the chain hard to follow by
    hand: which files are involved, which pulled in which, and where two of them
    disagree.

    `masked_by` is passed rather than measured here, because whose home is being
    reported on belongs to the caller — `resources/identity.py` asks about the
    session's home and this module has no session.
    """
    return {
        'files': [str(path) for path in layering.files],
        'includes': [
            {
                'source': str(include.source),
                'target': str(include.target),
                'condition': include.condition,
                'taken': include.taken,
            }
            for include in layering.includes
        ],
        'conflicts': [
            {
                'key': conflict.key,
                'files': conflict.files,
                'winner': {'origin': str(conflict.winner.origin), 'value': conflict.winner.value},
                'losers': [{'origin': str(setting.origin), 'value': setting.value} for setting in conflict.losers],
            }
            for conflict in layering.conflicts
        ],
        'masked_by': str(masked_by) if masked_by else None,
    }


def render(layering: Layering, console) -> None:  # noqa: ANN001 — a rich Console, imported by the caller
    """The include chain as a tree, and what each file contributed.

    A tree because the arrangement *is* one and `git config --list --show-origin`
    is the flat projection of it that prompted this: it prints every leaf with the
    file beside it and no way to see that the file was reached through three
    others, so a setting appearing twice reads as a repetition rather than as one
    file overriding another.

    Each file is shown with how many settings it contributed. That is what
    separates a file that is doing nothing from one that is absent, and both from
    the conditional include that exists and did not fire.
    """
    contributed: dict[Path, int] = {}
    for setting in layering.settings:
        contributed[setting.origin] = contributed.get(setting.origin, 0) + 1

    edges: dict[Path, list[Include]] = {}
    for include in layering.includes:
        edges.setdefault(include.source, []).append(include)

    roots = [path for path in layering.files if path not in {include.target for include in layering.includes}]
    for root in roots:
        console.print(f'[bold]{root.name}[/]  {_state(root, contributed)}')
        _branch(root, edges, contributed, console, prefix='')

    if not layering.conflicts:
        return
    console.print()
    console.print('[bold yellow]set in more than one file[/]')
    for conflict in layering.conflicts:
        console.print(f'  [bold]{conflict.key}[/]')
        # The losers plain and the winner coloured, rather than the losers faint.
        # Faint is unreadable on half the themes this fleet uses, and these rows
        # are the evidence for the finding — the one that must stay legible is
        # the value being overridden, not the one already in effect.
        for setting in conflict.losers:
            console.print(f'    {setting.origin.name:<22} {quoted(setting.value)}  overridden')
        console.print(f'    [green]{conflict.winner.origin.name:<22} {quoted(conflict.winner.value)}[/]  wins')


def _state(path: Path, contributed: dict[Path, int]) -> str:
    """What one file is doing, in the three states worth telling apart.

    Absent is a normal state rather than a fault. Each overlay gitconfig is named
    for the coordinate value that ships it, and `common.gitconfig` names every one
    it knows of, so a machine lists the values it is not as well as the ones it
    is: `wsl.gitconfig` absent on a native machine is the design working. git
    ignores an include whose target is not there, which is what makes the scheme
    optional per axis and lets one shared file name every value.

    The three are told apart by what they say, not by how faintly they are
    printed. Every one of them is an ordinary state, so none earns a colour, and
    faint is unreadable on half the themes this fleet uses.
    """
    if not path.exists():
        return 'absent — nothing declares one for this machine'
    if count := contributed.get(path, 0):
        return f'{count} setting(s)'
    return 'no settings'


def _branch(path: Path, edges: dict[Path, list[Include]], contributed: dict[Path, int], console, prefix: str) -> None:  # noqa: ANN001
    """Everything one file pulls in, depth first. The caller prints the file."""
    children = edges.get(path, [])
    for index, include in enumerate(children):
        last = index == len(children) - 1
        condition = f'  [yellow]if {include.condition}[/]' if include.condition else ''
        skipped = '' if include.taken or not include.target.exists() else '  [yellow]— condition did not hold here[/]'
        console.print(
            f'{prefix}{"└─ " if last else "├─ "}[bold]{include.target.name}[/]  {_state(include.target, contributed)}{condition}{skipped}'
        )
        _branch(include.target, edges, contributed, console, prefix=f'{prefix}{"   " if last else "│  "}')


def _parse(payload: str) -> list[Setting]:
    """Split git's NUL-delimited listing into settings.

    `-z` rather than the line format, because a value is free to contain both a
    newline and a tab and the aliases here do contain spaces. With it, records
    alternate origin and body, and the body splits key from value at the first
    newline — a body with none is a key set with no value at all, which git
    reports as an empty string and means `true`.
    """
    records = [record for record in payload.split('\0') if record]
    settings = []
    for index in range(0, len(records) - 1, 2):
        origin, body = records[index], records[index + 1]
        if not origin.startswith('file:'):
            # A value from the command line or an environment variable has no file
            # behind it, so there is nothing for a layering to say about it.
            continue
        key, _, value = body.partition('\n')
        settings.append(Setting(Path(origin.removeprefix('file:')), key, value))
    return settings
