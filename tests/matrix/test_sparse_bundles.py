"""A bundle that carries less, and the three answers an absence can have.

The whole point of `bundle.json`: under a full bundle an absent tool is a gap,
and reading a sparse bundle's deliberate omissions the same way reports a working
machine as missing most of itself. That is the sweep-as-deletion failure
`standards/cli-design.md` measures on todoui, and these are the tests that keep
this side of it closed.

Three states, and each one is asserted separately because the middle one is new
and the other two are what it must not become:

    in the manifest       install it from the staging directory
    in `current`          MATCHED at the version the builder measured
    in neither            UNKNOWN, and honest about why

Driven through the CLI against a real staged bundle, so what is asserted is what
an offline run on the target would decide.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles import create_bundle
from dotfiles import status as status_document
from dotfiles.providers import bundle
from dotfiles.vocabulary import ExitCode
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import LAZYGIT
from matrix.harness import Invocation
from matrix.harness import Sandbox

INSTALLED = '0.45.0'


def status_for(machine: str = 'box', **installed: str) -> dict[str, object]:
    """A status document shaped the way `status show --json` shapes one."""
    return {
        'version': status_document.VERSION,
        'verb': 'plan',
        'machine': machine,
        'checked': '2026-09-09T12:00:00+00:00',
        'scope': ['packages', 'toolchains'],
        'verdict': 'converged',
        'resources': [
            {
                'address': 'packages',
                'verdict': 'converged',
                'detail': '',
                'examined': [{'item': f'github-release/{name}', 'detail': version, 'group': ''} for name, version in installed.items()],
            }
        ],
    }


class TestReadingAStatus:
    def test_the_installed_versions_are_keyed_on_the_tool_name(self) -> None:
        """A row's `item` is the address a plan uses, and a bundle row is keyed on
        the name — so the provider half is dropped once, here."""
        found = create_bundle.installed_versions(status_for(lazygit='0.45.0', fd='10.2.0'))

        assert found == {'lazygit': '0.45.0', 'fd': '10.2.0'}

    def test_a_document_of_the_wrong_generation_is_refused(self, tmp_path: Path) -> None:
        """Version 1 carried counts and no rows, so a builder handed one would find
        nothing installed anywhere and bundle the entire declaration — reporting it
        as a sparse build. Refusing beats a plausible wrong answer."""
        path = tmp_path / 'old.json'
        path.write_text(json.dumps({'version': 1, 'machine': 'box'}))

        with pytest.raises(create_bundle.BundleError, match='status document'):
            create_bundle.read_status(path)

    def test_an_unreadable_document_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / 'broken.json'
        path.write_text('{not json')

        with pytest.raises(create_bundle.BundleError, match='readable'):
            create_bundle.read_status(path)


class TestDecidingWhatToLeaveOut:
    def built(self, tmp_path: Path, **installed: str) -> create_bundle.Bundle:
        import datetime as dt

        made = create_bundle.Bundle(tmp_path / 'installers', 'linux', 'x86_64', 'box', dt.datetime(2026, 9, 9, tzinfo=dt.UTC))
        path = tmp_path / 'status.json'
        document = status_for(**installed)
        path.write_text(json.dumps(document))
        made.plan_against(path, document)
        return made

    def test_a_tool_at_the_version_upstream_publishes_is_left_out(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit=INSTALLED)

        assert made.already_current('binary', 'lazygit', INSTALLED) is True
        assert made.current == {'binary/lazygit': INSTALLED}

    def test_a_tool_behind_upstream_is_carried(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit='0.44.0')

        assert made.already_current('binary', 'lazygit', INSTALLED) is False
        assert made.current == {}

    def test_a_tool_the_target_does_not_have_is_carried(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, somethingelse='1.0.0')

        assert made.already_current('binary', 'lazygit', INSTALLED) is False

    def test_a_row_whose_detail_is_prose_rather_than_a_version_is_carried(self, tmp_path: Path) -> None:
        """The safe direction. A detail like "not installed" compares False, so the
        tool goes into the bundle rather than being declared current."""
        made = self.built(tmp_path, lazygit='not installed')

        assert made.already_current('binary', 'lazygit', INSTALLED) is False

    def test_a_full_build_leaves_nothing_out_however_current_the_target_is(self, tmp_path: Path) -> None:
        """Paired with the first case: without `--against` there is no premise to
        omit anything on, and a build that quietly did would be a sparse bundle
        describing itself as full."""
        import datetime as dt

        made = create_bundle.Bundle(tmp_path / 'installers', 'linux', 'x86_64', 'box', dt.datetime(2026, 9, 9, tzinfo=dt.UTC))

        assert made.already_current('binary', 'lazygit', INSTALLED) is False
        assert made.describe().completeness is bundle.Completeness.FULL

    def test_a_sparse_build_describes_itself_as_one(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit=INSTALLED)
        made.already_current('binary', 'lazygit', INSTALLED)

        described = made.describe()
        assert described.completeness is bundle.Completeness.SPARSE
        assert described.built_from == 'status.json'
        assert described.current == {'binary/lazygit': INSTALLED}


class TestWhatTheTargetDecides:
    """The three-way verdict, measured through `plan --offline` on the target."""

    def staged(self, sandbox: Sandbox, carried: dict[str, str], **described: object) -> None:
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle(carried, **described)  # type: ignore[arg-type]

    def test_a_carried_tool_is_measured_against_the_row(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        self.staged(sandbox, {'lazygit': '0.46.0'})
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert [row['verdict'] for row in rows if 'lazygit' in row['item']] == ['stale']

    def test_a_measured_tool_reports_nothing_rather_than_unmeasurable(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The whole point. A sparse bundle omits what the target already has, and
        the target has to read that omission as "current" rather than as "nobody
        can say"."""
        self.staged(sandbox, {}, sparse=True, current={'binary/lazygit': INSTALLED}, built_from='a-status.json')
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert not [row for row in rows if 'lazygit' in row['item']]

    def test_a_measured_tool_the_machine_has_since_moved_off_is_drift(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The premise expired. The bundle was planned when this machine had that
        version; it no longer does, and the existing comparison says so without a
        second mechanism."""
        self.staged(sandbox, {}, sparse=True, current={'binary/lazygit': '0.46.0'}, built_from='a-status.json')
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert [row['verdict'] for row in rows if 'lazygit' in row['item']] == ['stale']

    def test_a_tool_in_neither_is_unmeasurable_and_says_the_sparse_reason(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The third state, which is the one that must not collapse into the
        second: the declaration gained this after the status was taken, so nothing
        has ever measured it and calling it current would be a guess."""
        self.staged(sandbox, {}, sparse=True, current={'binary/somethingelse': '1.0.0'}, built_from='a-status.json')
        sandbox.installed('lazygit', INSTALLED)

        # `others` rather than `findings`: an unmeasurable row carries
        # `Repair.NONE`, so it is something the walk saw and neither verb keeps as
        # its own finding. It reaches `--json` all the same, which is the property
        # "a fact on screen is reachable through some machine door" states.
        ran = cli('check', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['others']]
        found = next(row for row in rows if 'lazygit' in row['item'])

        assert found['verdict'] == 'unknown'
        assert 'never considered' in found['detail']

    def test_a_full_bundle_keeps_the_old_reason(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The sparse wording must not reach a machine with no sparse bundle
        staged, where the honest answer is still that the bundle carries nothing."""
        self.staged(sandbox, {})
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('check', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['others']]
        found = next(row for row in rows if 'lazygit' in row['item'])

        assert found['verdict'] == 'unknown'
        assert 'carries no version' in found['detail']


class TestWhatBundleCheckReports:
    def test_a_measured_tool_is_neither_covered_nor_a_gap(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Counting it covered reports a bundle as able to repair something it does
        not hold; counting it uncovered reports a working machine as missing it."""
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({}, sparse=True, current={'binary/lazygit': INSTALLED}, built_from='a-status.json')

        ran = cli('bundle', 'check', '--json', catch_exceptions=True)

        assert ran.document['measured'] == ['lazygit']
        assert ran.document['uncovered'] == []
        assert ran.document['covered'] == []
        assert ran.document['sparse'] is True

    def test_an_unconsidered_tool_is_still_a_gap(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({}, sparse=True, current={'binary/somethingelse': '1.0.0'}, built_from='a-status.json')

        ran = cli('bundle', 'check', '--json', catch_exceptions=True)

        assert ran.document['uncovered'] == ['lazygit']
        assert ran.document['measured'] == []
        assert ran.exit_code == ExitCode.DRIFT
