"""`Change`: the one dataclass every resource builds, and the rule it enforces.

Nothing here touches a machine. `advice_for` and `repair_for` are pure
functions over a `DesiredItem` and a measured `Preconditions`, and the
`__post_init__` on `Change` is a validation rule worth testing on its own
rather than only through the resources that can trip it.
"""

from __future__ import annotations

import dataclasses as dc

import pytest

from dotfiles.plan import DesiredItem
from dotfiles.plan import Precondition
from dotfiles.plan import Preconditions
from dotfiles.plan import Reason
from dotfiles.plan import Stage
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import advice_for
from dotfiles.resources import repair_for


def item(precondition: Precondition = Precondition.NONE) -> DesiredItem:
    return DesiredItem(
        section='github_releases',
        provider='ghrelease',
        resource='packages',
        stage=Stage.TOOLS,
        name='learning',
        executable='learning',
        evidence_path='',
        precondition=precondition,
        entry=None,
        reason=Reason('github_releases', 'test'),
    )


def test_repair_is_answered_at_every_site_rather_than_by_omission() -> None:
    """The invariant the required field created, which nothing else asserts.

    Seventeen construction sites took `Repair.AUTOMATIC` by default, and being
    seventeen is what made a wrong one findable: a site that never asked who could
    fix its finding stood beside sites that had, so the omission had something to
    be read against. Making the field required removed that redundancy and put
    nothing in its place. Restore the default and every existing site goes on
    compiling, every test here goes on passing, and the next `Change` written
    afterwards promises `apply` can repair something it cannot — which is the
    whole of what a defaulted `repair` says.

    Asserted of the field rather than of a `TypeError` from a short call, because
    those are not the same claim. A short call raises `TypeError` for any change
    to the signature at all — a field reordered, a field renamed, a field added
    ahead of this one — so it can pass for the wrong reason as easily as fail for
    one, and it would go on passing if `repair` were defaulted and some other
    field became required in its place.

    Asserted of the field rather than of the call sites, because a restored
    default is invisible to a walk over sites that still pass `repair`
    explicitly. Every one of them would stay green, and the site that found out
    would be the one written next — which is exactly the delay the required field
    exists to remove.

    `detail`, `advice`, `observed` and `source` default legitimately, and the
    difference is what a default *means*. An empty `detail` is an absence: nothing
    was said. A defaulted `repair` is an answer — `apply` can fix this — given by a
    site that never considered the question, and `apply` acts on it.
    """
    fields = {field.name: field for field in dc.fields(Change)}
    repair = fields['repair']

    assert repair.default is dc.MISSING, 'Change.repair has a default again, so a site can answer it by omission'
    assert repair.default_factory is dc.MISSING, 'Change.repair has a default factory, so a site can answer it by omission'


def test_a_by_hand_change_with_no_advice_is_refused() -> None:
    """A refusal `apply` cannot act on has to leave a reader something to do, or
    it is a dead end rather than a finding."""
    with pytest.raises(ValueError, match='repair=BY_HAND'):
        Change('packages', Stage.TOOLS, 'ghrelease/learning', Verdict.MISSING, repair=Repair.BY_HAND)


def test_a_by_hand_change_with_advice_is_fine() -> None:
    change = Change('packages', Stage.TOOLS, 'ghrelease/learning', Verdict.MISSING, repair=Repair.BY_HAND, advice='log in')
    assert change.advice == 'log in'


def test_advice_is_optional_off_by_hand() -> None:
    """Nothing about `AUTOMATIC` or `NONE` needs a next step: `apply` is the next
    step, or there is nothing to measure."""
    Change('packages', Stage.TOOLS, 'ghrelease/lazygit', Verdict.MISSING, repair=Repair.AUTOMATIC)
    Change('packages', Stage.TOOLS, 'ghrelease/lazygit', Verdict.UNKNOWN, repair=Repair.NONE)


def test_as_dict_carries_advice() -> None:
    change = Change('packages', Stage.TOOLS, 'x', Verdict.MISSING, repair=Repair.BY_HAND, advice='do it')
    assert change.as_dict()['advice'] == 'do it'


def test_advice_for_a_repair_that_is_not_by_hand_is_empty() -> None:
    assert advice_for(item(), Repair.AUTOMATIC) == ''
    assert advice_for(item(), Repair.NONE) == ''


def test_advice_for_an_unmet_github_login_names_the_command() -> None:
    advice = advice_for(item(Precondition.GITHUB_AUTH), Repair.BY_HAND)
    assert 'gh auth login' in advice


def test_advice_for_a_missing_amd_gpu_says_theres_nothing_to_do() -> None:
    advice = advice_for(item(Precondition.AMD_GPU), Repair.BY_HAND)
    assert 'AMD GPU' in advice


def test_repair_for_and_advice_for_agree_on_every_precondition() -> None:
    """`repair_for` deciding `BY_HAND` and `advice_for` having nothing to say
    about it is exactly the gap the `Change` constructor now refuses to let
    through — proven here for every declared `Precondition`, not only the two
    presently in use, so a new member added to one and not the other fails at
    the first `Change` it reaches rather than shipping silent."""
    met = Preconditions(github_auth=False, amd_gpu=False)
    for precondition in Precondition:
        if precondition is Precondition.NONE:
            continue
        repair = repair_for(item(precondition), Verdict.MISSING, met)
        assert repair is Repair.BY_HAND
        assert advice_for(item(precondition), repair) != ''
