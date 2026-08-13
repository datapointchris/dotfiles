"""The grammar is a contract, so it is asserted rather than reviewed.

Every command in the tree is walked and its name checked against the closed
vocabulary in `dotfiles.vocabulary`. That makes adding a verb an edit to a
documented list with a written reason, instead of something that happens by
accident on one subcommand and nowhere else — which is how `link`/`relink`,
`--dry-run`, `--force` and `--mine` each came to mean something slightly
different depending on where they were typed.

These tests never invoke a command. They inspect the built app, so nothing here
touches the machine.
"""

from __future__ import annotations

import click
import pytest
from typer.main import get_command

from dotfiles import vocabulary
from dotfiles.main import app


def walk(command: click.Command, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], click.Command]]:
    """Every command in the tree, with the path it is reached by."""
    found = [(path, command)] if path else []
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            found.extend(walk(child, (*path, name)))
    return found


TREE = walk(get_command(app))
LEAVES = [(path, cmd) for path, cmd in TREE if not isinstance(cmd, click.Group)]
GROUPS = [(path, cmd) for path, cmd in TREE if isinstance(cmd, click.Group)]


RECONCILING = [(path, command) for path, command in LEAVES if path[-1] in {'plan', 'check', 'apply'}]
"""Every `plan`, `check` and `apply` in the tree, with no exceptions carved out.

The first cut of this rule kept `network check`, `bundle check` and the two under
`windows` outside it, on the stated grounds that none of them emits through
`effects`. That was measured afterwards and is false: `network.py` and
`windows.py` reference `effects` six and four times, and `offline_bundle.py`
twice. Only `machines check` really does not, and `-q` still means something there
because the finding rows it suppresses are rendered the same way.

So the rule is the verb, not the subject. A reader who learns `-v` on one
`check` has learned it everywhere, which is worth more than sparing four leaves a
flag."""


def test_the_tree_is_not_empty() -> None:
    """Guards every other test here: a walk that finds nothing passes vacuously."""
    assert len(LEAVES) > 20
    assert len(GROUPS) == len(vocabulary.NOUNS)
    assert len(RECONCILING) > 15


@pytest.mark.parametrize(('path', 'command'), RECONCILING, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_reconciling_leaf_takes_the_verbosity_pair(path: tuple[str, ...], command: click.Command) -> None:
    """A flag that works on `dotfiles apply` and not on `dotfiles packages apply`
    is the drift this file exists to catch — the same asymmetry `--dry-run` and
    `--force` had, one subcommand at a time."""
    flags = {name for param in command.params for name in param.opts}
    assert {'-v', '--verbose'} <= flags, f'`dotfiles {" ".join(path)}` cannot be turned up'
    assert {'-q', '--quiet'} <= flags, f'`dotfiles {" ".join(path)}` cannot be quietened'


@pytest.mark.parametrize(('path', 'command'), LEAVES, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_leaf_is_a_documented_verb(path: tuple[str, ...], command: click.Command) -> None:
    verb = path[-1]
    assert verb in vocabulary.VERBS, (
        f'`dotfiles {" ".join(path)}` uses the verb {verb!r}, which is not in the closed vocabulary. '
        f'Add it to CORE_VERBS, or to EXCEPTION_VERBS with the reason it cannot be one of '
        f'{vocabulary.CORE_VERBS}.'
    )


@pytest.mark.parametrize(('path', 'group'), GROUPS, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_group_is_a_documented_noun(path: tuple[str, ...], group: click.Group) -> None:
    assert path[-1] in vocabulary.NOUNS


def test_every_documented_exception_is_actually_used() -> None:
    """An exception nobody uses is a licence left lying around.

    The list is what a reviewer reads to decide whether a new verb is justified,
    so a stale entry makes the bar look lower than it is.
    """
    used = {path[-1] for path, _ in LEAVES}
    unused = set(vocabulary.EXCEPTION_VERBS) - used
    assert not unused, f'documented but unused: {sorted(unused)}'


def test_every_resource_offers_check() -> None:
    """`check` is what makes a resource a resource: it can say whether it matches."""
    leaves = {(path[0], path[-1]) for path, _ in LEAVES if len(path) == 2}
    for resource in vocabulary.RESOURCES:
        assert (resource, 'check') in leaves, f'{resource} has no check'


CHECKED_ONLY = {'identity', 'auth', 'credentials'}
"""The resources with nothing for `apply` to write, and the reason is nearly the
same for all three: what they measure is personal and arrives by hand. An identity
is per-machine, so the repo holds no value for it; a login is a browser flow, a
password or a device code, so `apply` attempting one would put a prompt in front
of every headless box. `credentials` is the odd one — its findings are not
personal but they are not the repo's either, since a helper that will not start is
a fault in the machine underneath git. Naming them here is what stops `apply`
being added to any of them later on the grounds that the set looked incomplete."""


def test_apply_exists_wherever_drift_can_be_fixed() -> None:
    leaves = {(path[0], path[-1]) for path, _ in LEAVES if len(path) == 2}
    for resource in vocabulary.RESOURCES:
        has_apply = (resource, 'apply') in leaves
        assert has_apply is (resource not in CHECKED_ONLY), f'{resource}: unexpected apply={has_apply}'


def test_machine_and_offline_bind_to_leaves_not_groups() -> None:
    """Click parses group options before the subcommand name, so `dotfiles apply
    --machine X` — the exact line a bootstrap runs — would raise `No such option`
    if these were declared on the callback."""
    for path, group in GROUPS:
        names = {option for parameter in group.params for option in parameter.opts}
        assert '--machine' not in names, f'{"/".join(path) or "root"} declares --machine on the group'
        assert '--offline' not in names, f'{"/".join(path) or "root"} declares --offline on the group'


SELECTORS = ('--machine', '--source', '--owner', '--offline')
"""Options that narrow *what* a verb covers, rather than how it writes.

`--offline` belongs here despite reading as a write instruction: under the flag the
staged bundle *is* the upstream every currency verdict is measured against, so it
changes what the answer is rather than narrowing the write. A plan that ignores it
rehearses a different run, which is the defect this test exists for.

`--reinstall` is the genuine member of the other group. It names work to do again
whatever measuring concludes, so there is no reading of a machine it could change.
"""


def test_plan_accepts_every_selector_its_apply_does() -> None:
    """`plan` answers "what would `apply` change", so a scope the write accepts and
    the read cannot express is not a narrower preview — it is no preview at all.

    Measured before this held: `packages apply` took `--source` and `--owner` while
    `packages plan` took neither, so the narrow write most worth rehearsing was the
    one with no rehearsal available. Asserted across the tree rather than for that
    pair, because the gap opened by adding a selector to one verb and forgetting
    the other, and nothing but this notices.
    """
    accepted = {path: {option for parameter in command.params for option in parameter.opts} for path, command in LEAVES}
    for path, options in accepted.items():
        if path[-1] != 'apply' or (preview := accepted.get((*path[:-1], 'plan'))) is None:
            continue
        missing = {selector for selector in SELECTORS if selector in options} - preview
        assert not missing, f'{"/".join(path)} accepts {sorted(missing)}, which its plan cannot express'


OFFLINE_MEANS_NOTHING_TO_CHECK = {('windows',)}
"""Verbs whose `check` reaches no network, so a bundle cannot change its answer.

`windows check` asks which of a fixed set of filenames exist in one directory. It
needs neither winget nor a network, which is what let it become a real checker at
all — so `--offline` would be a flag that changes nothing. Its `apply` takes one
because installing is where winget is reached.

Named rather than left to fall out of the loop, so the next reader knows the pair
was considered rather than missed.
"""


def test_check_takes_offline_wherever_apply_does() -> None:
    """`--offline` swaps the upstream for a staged bundle, so it changes what every
    verb *answers* rather than narrowing what one covers.

    Asserted for this flag alone, and not by widening the selector test above.
    `check` deliberately does not take `--source` or `--owner` — that was decided
    against on the symmetry argument, because narrowing what is examined is a
    different act from changing what the examination compares against. Nothing
    pinned this pair, so `dotfiles check --offline` existed while
    `dotfiles packages check --offline` did not, and the test written for exactly
    this class of gap could not see it.
    """
    accepted = {path: {option for parameter in command.params for option in parameter.opts} for path, command in LEAVES}
    for path, options in accepted.items():
        if path[-1] != 'apply' or '--offline' not in options or path[:-1] in OFFLINE_MEANS_NOTHING_TO_CHECK:
            continue
        examined = accepted.get((*path[:-1], 'check'))
        if examined is None:
            continue
        assert '--offline' in examined, f'{"/".join(path)} takes --offline, which its check cannot express'


def test_no_leaf_offers_dry_run() -> None:
    """`check` is `apply` with the last step not run, so there is no code path a
    flag could switch off. A `--dry-run` would have to be a second implementation."""
    for path, command in LEAVES:
        names = {option for parameter in command.params for option in parameter.opts}
        assert '--dry-run' not in names, f'{"/".join(path)} offers --dry-run'
