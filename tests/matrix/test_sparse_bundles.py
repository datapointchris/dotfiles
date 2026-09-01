"""A bundle that carries less, and the four answers an absence can have.

The whole point of `bundle.json`: under a full bundle an absent tool is a gap,
and reading a sparse bundle's deliberate omissions the same way reports a working
machine as missing most of itself. That is the sweep-as-deletion failure
`standards/cli-design.md` measures on todoui, and these are the tests that keep
this side of it closed.

Four states, each asserted separately because they are what the others must not
collapse into:

    in the manifest       install it from the staging directory
    in `current`          MATCHED at the version the builder measured
    in neither            UNKNOWN, and honest about which bundle is missing it
    no bundle carries it  UNKNOWN, with no fix offered, because none exists

Driven through the CLI against a real staged bundle, so what is asserted is what
an offline run on the target would decide.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles import create_bundle
from dotfiles import status as status_document
from dotfiles.providers import bundle
from dotfiles.vocabulary import ExitCode
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import DECLARES_SYNCER
from matrix.harness import DECLARES_VENDOR_INSTALLER
from matrix.harness import LAZYGIT
from matrix.harness import SYNCER
from matrix.harness import VENDOR_INSTALLER
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
                'examined': [{'item': f'ghrelease/{name}', 'detail': version, 'group': ''} for name, version in installed.items()],
            }
        ],
    }


class TestReadingAStatus:
    def test_the_installed_versions_are_keyed_on_the_plan_address(self) -> None:
        """The whole `provider/name`, because that is the identity the rest of the
        chain uses. Two providers naming one tool would otherwise collapse into
        whichever resource was walked last."""
        found = create_bundle.installed_versions(status_for(lazygit='0.45.0', fd='10.2.0'))

        assert found == {'ghrelease/lazygit': '0.45.0', 'ghrelease/fd': '10.2.0'}

    def test_a_changed_row_answers_where_examined_is_empty(self) -> None:
        """The case that made every sparse build a full one. `_unreported` drops an
        item that produced a change, and offline every tool with no bundle row is
        UNKNOWN — so on a target with nothing staged `examined` is empty and the
        versions are all in `others`."""
        document = status_for()
        resource = document['resources'][0]  # type: ignore[index]
        resource['others'] = [{'item': 'ghrelease/lazygit', 'observed': '0.45.0', 'verdict': 'unknown'}]  # type: ignore[index]

        found = create_bundle.installed_versions(document)

        assert found == {'ghrelease/lazygit': '0.45.0'}

    def test_an_examined_row_wins_over_a_changed_one(self) -> None:
        """`detail` on an examined row is the measured version. Where an item
        appears twice the measured one is the answer."""
        document = status_for(lazygit='0.45.0')
        resource = document['resources'][0]  # type: ignore[index]
        resource['others'] = [{'item': 'ghrelease/lazygit', 'observed': '0.44.0', 'verdict': 'unknown'}]  # type: ignore[index]

        found = create_bundle.installed_versions(document)

        assert found == {'ghrelease/lazygit': '0.45.0'}

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

    def test_a_document_covering_nothing_bundlable_is_refused(self, tmp_path: Path) -> None:
        """One shape comes from three widths, so a valid version 2 can say nothing
        about packages. Accepted, it measures nothing, carries everything, and is
        named `-sparse` — and a `-sparse` name is what stops `base_of` pinning the
        only complete bundle on a box that cannot fetch another."""
        path = tmp_path / 'symlinks.json'
        path.write_text(json.dumps({'version': 2, 'machine': 'box', 'scope': ['symlinks'], 'resources': []}))

        with pytest.raises(create_bundle.BundleError, match='packages'):
            create_bundle.read_status(path)

    def test_a_document_covering_one_of_the_two_is_enough(self, tmp_path: Path) -> None:
        """Paired with the refusal above. A resource-scoped `packages` document is
        a legitimate premise and a check that wanted both would reject it."""
        path = tmp_path / 'packages.json'
        path.write_text(json.dumps({'version': 2, 'machine': 'box', 'scope': ['packages'], 'resources': []}))

        assert create_bundle.read_status(path)['scope'] == ['packages']

    def test_a_document_naming_no_scope_at_all_is_still_read(self, tmp_path: Path) -> None:
        """`scope` is additive and documents published before it exist. Refusing
        one would break the machines the loop is already running on."""
        path = tmp_path / 'unscoped.json'
        path.write_text(json.dumps({'version': 2, 'machine': 'box', 'resources': []}))

        assert create_bundle.read_status(path)['machine'] == 'box'


class TestDecidingWhatToLeaveOut:
    def built(self, tmp_path: Path, **installed: str) -> create_bundle.Bundle:
        made = create_bundle.Bundle(tmp_path / 'installers', 'linux', 'x86_64', 'box', dt.datetime(2026, 9, 9, tzinfo=dt.UTC))
        path = tmp_path / 'status.json'
        document = status_for(**installed)
        path.write_text(json.dumps(document))
        made.plan_against(path, document)
        return made

    def test_a_tool_at_the_version_upstream_publishes_is_left_out(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit=INSTALLED)

        assert made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED) is True
        assert made.current == {'binary/lazygit': INSTALLED}

    def test_a_tool_behind_upstream_is_carried(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit='0.44.0')

        assert made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED) is False
        assert made.current == {}

    def test_a_tool_the_target_does_not_have_is_carried(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, somethingelse='1.0.0')

        assert made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED) is False

    def test_a_row_whose_detail_is_prose_rather_than_a_version_is_carried(self, tmp_path: Path) -> None:
        """The safe direction. A detail like "not installed" compares False, so the
        tool goes into the bundle rather than being declared current."""
        made = self.built(tmp_path, lazygit='not installed')

        assert made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED) is False

    def test_a_full_build_leaves_nothing_out_however_current_the_target_is(self, tmp_path: Path) -> None:
        """Paired with the first case: without `--against` there is no premise to
        omit anything on, and a build that quietly did would be a sparse bundle
        describing itself as full."""

        made = create_bundle.Bundle(tmp_path / 'installers', 'linux', 'x86_64', 'box', dt.datetime(2026, 9, 9, tzinfo=dt.UTC))

        assert made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED) is False
        assert made.describe().completeness is bundle.Completeness.FULL

    def test_a_sparse_build_describes_itself_as_one(self, tmp_path: Path) -> None:
        made = self.built(tmp_path, lazygit=INSTALLED)
        made.already_current('ghrelease', 'binary', 'lazygit', INSTALLED)

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

    def test_a_tool_measured_under_a_second_category_is_still_read(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The key carries a category, and the reader has to search every one the
        bundler writes.

        `winget` was missing from that list while `add_winget_binaries` was one of
        the four writers of `current`, so a sparse bundle for a Windows manifest
        recorded `winget/rg` and every lookup searched past it — reporting a tool
        the builder had measured as one nothing could measure.
        """
        self.staged(sandbox, {}, sparse=True, current={'winget/lazygit': INSTALLED}, built_from='a-status.json')
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert not [row for row in rows if 'lazygit' in row['item']]

    def test_a_newer_sparse_bundle_outranks_an_older_full_one(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The stack this feature builds, and the one shape nothing covered.

        A sparse bundle carries no row for a tool it measured, so an older full
        bundle's row survives the merge in `rows()`. Asking every bundle for a row
        before any bundle for its `current` then ranks by kind of answer rather
        than by age: the machine is told it is ahead of the newest release, and
        `apply --offline` repairs that by reinstalling the older binary the full
        bundle still holds.
        """
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({'lazygit': '0.44.0'}, name='dotfiles-offline-v20260101T000000Z-box-linux-x86_64')
        sandbox.stage_bundle(
            {},
            name='dotfiles-offline-v20260201T000000Z-box-linux-x86_64-sparse',
            sparse=True,
            current={'binary/lazygit': INSTALLED},
            built_from='a-status.json',
        )
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


class TestNamingWhereTheFigureCameFrom:
    """Offline the upstream is one tarball, and the row has to say so.

    `the newest release` is a claim about what upstream publishes. Offline it is a
    claim about what a builder resolved on the day the bundle was built, and the
    two are the same sentence only while the bundle is fresh.
    """

    def test_ahead_of_the_bundle_says_apply_will_install_the_older_build(self, sandbox: Sandbox, cli) -> None:
        """The sentence that hid a real downgrade. A fortnight-old bundle staged
        under a newer one that never unpacked took broot from 1.59.0 back to
        1.58.0, and the plan above it read as an ordinary repair."""
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({'lazygit': '0.44.0'})
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]
        found = next(row for row in rows if 'lazygit' in row['item'])

        assert 'what the staged bundle carries' in found['detail']
        assert 'applying installs that older build' in found['detail']

    def test_behind_the_bundle_names_the_bundle_rather_than_upstream(self, sandbox: Sandbox, cli) -> None:
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({'lazygit': '0.46.0'})
        sandbox.installed('lazygit', INSTALLED)

        ran = cli('plan', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert next(row for row in rows if 'lazygit' in row['item'])['detail'] == '0.46.0 is what the staged bundle carries'

    def test_online_the_wording_still_names_the_release(self, sandbox: Sandbox, cli) -> None:
        """The online sentence is correct and stays. Two sources, two sentences."""
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.installed('lazygit', INSTALLED)
        sandbox.upstream({'jesseduffield/lazygit': '0.46.0'})

        ran = cli('plan', '--cached', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert next(row for row in rows if 'lazygit' in row['item'])['detail'] == '0.46.0 is the latest release'


class TestWhatNoBundleEverCarries:
    """The fourth state, and the one that read as a fault on every offline run.

    A `uv tool install` from git, an apt package, an npm global, a vendor installer
    fetched at install time — no bundle is built to hold any of them, so a bundle
    having no row is not an absence to repair. Read as a bundle gap it advises
    extracting a newer bundle, which is a fix that does not exist.
    """

    def staged(self, sandbox: Sandbox) -> None:
        """A tool behind its upstream, on a machine with a bundle that cannot say so."""
        sandbox.declare(packages=SYNCER, manifest=DECLARES_SYNCER)
        sandbox.stage_bundle({'lazygit': '0.46.0'})
        sandbox.installed('syncer')
        sandbox.uv_installed('syncer', pin='v11.3.2')
        sandbox.upstream({'datapointchris/syncer': 'v12.0.0'})

    def row(self, ran: Invocation) -> dict[str, str]:
        rows = [row for resource in ran.document['resources'] for row in resource['others']]
        return next(row for row in rows if 'syncer' in row['item'])

    def test_offline_the_row_names_the_kind_rather_than_the_bundle(self, sandbox: Sandbox, cli) -> None:
        self.staged(sandbox)

        found = self.row(cli('check', '--offline', '--json', catch_exceptions=True))

        assert found['verdict'] == 'unknown'
        assert 'no bundle carries a git uv tool' in found['detail']

    def test_offline_it_offers_no_fix_because_none_exists(self, sandbox: Sandbox, cli) -> None:
        """Advising a newer bundle is a permanent instruction that never resolves,
        which is what a reader reads as a fault in the machine."""
        self.staged(sandbox)

        assert self.row(cli('check', '--offline', '--json', catch_exceptions=True))['advice'] == ''

    def test_offline_the_run_still_counts_itself_blind(self, sandbox: Sandbox, cli) -> None:
        """Dropping the row would report `unmeasured: 0` and `converged` for a
        resource where a declared tool was never compared against anything, which
        converts *I could not measure this* into *I measured it and it was fine*."""
        self.staged(sandbox)

        ran = cli('check', '--offline', '--json', catch_exceptions=True)
        packages = next(r for r in ran.document['resources'] if r['address'] == 'packages')

        assert packages['unmeasured'] == 1

    def test_a_vendor_installer_is_blamed_on_its_own_entry_not_its_section(self, sandbox: Sandbox, cli) -> None:
        """`custom_installers` answers per entry, so a machine's bundle can carry
        five of them and miss this one. Naming the section states something false
        about the five, and the row offers no fix either way."""
        sandbox.declare(packages=VENDOR_INSTALLER, manifest=DECLARES_VENDOR_INSTALLER)
        sandbox.stage_bundle({'lazygit': '0.46.0'})
        sandbox.installed('terraform-ls', '0.39.0')

        ran = cli('check', '--offline', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['others']]
        found = next(row for row in rows if 'terraform-ls' in row['item'])

        assert 'terraform-ls declares no bundle_install_script' in found['detail']
        assert 'custom installer' not in found['detail']

    def test_online_the_same_tool_is_judged_stale(self, sandbox: Sandbox, cli) -> None:
        """The gate is the upstream in hand, never the entry kind. With a release
        cache to ask, the finding this bundle could not reach comes straight back."""
        self.staged(sandbox)

        ran = cli('plan', '--cached', '--json', catch_exceptions=True)
        rows = [row for resource in ran.document['resources'] for row in resource['findings']]

        assert [row['verdict'] for row in rows if 'syncer' in row['item']] == ['stale']


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
