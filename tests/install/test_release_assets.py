"""Every release names one finished file, for every target a machine here asks for.

`test_release_urls.py` is what knows whether a spelling is *right*: it asks the
release. That costs an API call per entry and is gated behind `--e2e`, so on a
normal run nothing calls these functions at all — the developer's own platform
gets resolved by whatever else happens to run, and the other three targets are
named by code no test executes.

The half that needs no network is the *shape* of the answer, and it is the half
that fails silently. A `{version}` left in a name 404s. A `cli/` tag reaching the
asset name puts a slash in a filename and addresses a path no release has. An arm
branch that stops being reachable fetches an Intel binary onto an Apple Silicon
box and reports it installed. None of that needs a release to see, and every one
of them is invisible from whichever machine the suite runs on.

So the table drives itself: every entry in `ASSETS` against every target, with no
expected filename written down anywhere. A tool added tomorrow is covered the day
it lands, and a test naming its asset would be the same string typed twice.
"""

from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath

import pytest

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import releases as providers
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import ReleaseArtifact

REPO_ROOT = Path(__file__).resolve().parents[2]

RELEASE_FAMILIES = (OSFamily.DARWIN, OSFamily.LINUX)
"""The two families an asset is named for.

`OSFamily` has a third member and not one function here branches on it, which the
windows manifest already records as the reason it declares no releases —
`test_a_windows_target_is_a_linux_target_to_every_one_of_these` is what holds that
line rather than a comment.
"""

TARGETS = tuple(Target(family, arch) for family in RELEASE_FAMILIES for arch in Arch)
"""Both architectures on both systems, including the linux arm64 no machine here
runs: `atuin` and `hadolint` each carry a linux arm branch, and it is reachable
from nothing else."""

ENTRIES = tuple(sorted(providers.ASSETS))

DECLARED = {entry.name: entry for entry in catalog.load().section('github_releases')}

CORPUS = tuple((entry, target) for entry in ENTRIES for target in TARGETS)


def case_id(value: str | Target) -> str:
    return value if isinstance(value, str) else f'{value.os_family}-{value.arch}'


def tag_for(entry: str, version: str = 'v1.2.3') -> str:
    """A tag shaped the way this entry's releases are tagged.

    The prefix comes off the declaration rather than a list here, because that is
    the half of a tag this repo owns: `release_tag_prefix` is what
    `ghrelease.resolve_tag` puts in front of a version, and the four data CLIs are
    tagged `cli/v…` because the same repo also releases an app.
    """
    return f'{DECLARED[entry].release_tag_prefix}{version}'


def artifact(entry: str, target: Target, version: str = 'v1.2.3') -> ReleaseArtifact:
    return providers.ASSETS[entry](tag_for(entry, version), target)


def strings(asset: ReleaseArtifact) -> tuple[str, ...]:
    """Every field of an artifact that ends up as a path on disk or in a URL."""
    return (asset.name, asset.path, asset.unit, *asset.extras)


def families_asked_for() -> dict[str, frozenset[OSFamily]]:
    """Which OS families a machine in this repo actually installs each release on.

    Read through `machine.subscription(...).wants` rather than off the manifests'
    keys, for `test_release_urls.build_corpus`'s reason: `true` means the whole
    section and a list means membership, so re-reading the key would be a second
    copy of that grammar and the copy that goes wrong first.

    It is what scopes the two distinctness rules below to something true. atuin
    names a linux triple on both branches and win32yank is one Windows binary —
    neither is a broken branch, and no manifest asks for either on a Mac.
    """
    declared = catalog.load()
    found: dict[str, set[OSFamily]] = {}
    for name in machines.names(REPO_ROOT):
        machine = machines.load(name, REPO_ROOT)
        for entry in declared.section('github_releases'):
            if machine.subscription('github_releases').wants(entry):
                found.setdefault(entry.name, set()).add(machine.coordinates.os_family)
    return {entry: frozenset(families) for entry, families in found.items()}


ASKED_FOR = families_asked_for()

ON_BOTH_SYSTEMS = tuple(entry for entry in ENTRIES if set(RELEASE_FAMILIES) <= ASKED_FOR.get(entry, frozenset()))

ON_DARWIN = tuple(entry for entry in ENTRIES if OSFamily.DARWIN in ASKED_FOR.get(entry, frozenset()))

PREFIXED_TAGS = tuple(entry for entry in ENTRIES if DECLARED[entry].release_tag_prefix)

UNIVERSAL_ON_DARWIN = {
    'ntfy': 'publishes one darwin_all asset, so an Apple Silicon box and an Intel one fetch the same file',
}
"""Entries exempt from the mac-architecture rule, each with what makes it exempt.

A row, not a function: a second tool going universal is one line here saying so,
and an exemption granted any other way is indistinguishable from the dead branch
the rule exists to catch. Each is held to producing one *artifact* rather than two
spellings of one name, which is the difference between universal and half-branched.
"""


def observed_archive(name: str) -> Archive:
    """What a filename says it is packed as, read the way an extractor reads it.

    Derived from the name rather than compared against a table of declared kinds,
    so the two sides are independent. `RAW` is the absence of every extension and
    gets no row of its own: a bare binary is named whatever upstream felt like,
    `hadolint-linux-x86_64` beside `yq_linux_amd64`.
    """
    if name.endswith(('.tar.gz', '.tar.xz', '.tgz')):
        return Archive.TARBALL
    if name.endswith('.zip'):
        return Archive.ZIP
    if name.endswith('.gz'):
        return Archive.GZIP
    return Archive.RAW


UNPACKED = (Archive.TARBALL, Archive.ZIP)
"""The kinds that yield more than one file, and so have to say which one to take."""


# ─────────────────────────────────────────────────────────────────────────────
# What every asset function owes, for every target
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(('entry', 'target'), CORPUS, ids=case_id)
def test_an_asset_is_named_in_full_rather_than_from_a_template(entry: str, target: Target) -> None:
    """A placeholder that survives is a 404 at install time and nothing sooner.

    `path`, `unit` and `extras` are covered as well as the name. `expand_pattern`
    lives in this module for the two sections that name assets from data, and an
    entry reaching for it would leave the same brace in whichever field it filled.
    """
    for value in strings(artifact(entry, target)):
        assert '{' not in value and '}' not in value, f'{entry} on {case_id(target)} left a placeholder in {value!r}'


@pytest.mark.parametrize(('entry', 'target'), CORPUS, ids=case_id)
def test_an_asset_name_is_one_segment_of_a_download_url(entry: str, target: Target) -> None:
    """`asset_url` puts this string last in a path, so a slash inside it addresses
    a file no release has — which is exactly what a `cli/` tag reaching the name
    would do for the four CLIs whose repos release two things under one tag space.
    """
    name = artifact(entry, target).name

    assert name, f'{entry} named no asset for {case_id(target)}'
    assert '/' not in name, f'{entry} named {name!r} for {case_id(target)}, which is a path rather than a filename'
    assert name == name.strip() and ' ' not in name, f'{entry} named {name!r} for {case_id(target)}'


@pytest.mark.parametrize(('entry', 'target'), CORPUS, ids=case_id)
def test_the_archive_kind_agrees_with_the_extension_it_names(entry: str, target: Target) -> None:
    """`_place` dispatches on the kind and never looks at the name.

    Two of the four decide what runs: a `.zip` declared `GZIP` is handed to gunzip
    and a tarball declared `RAW` is installed as the binary. The other two are
    asserted for the same reason even though the installer survives a mislabel —
    the table is what a reader believes about the release.
    """
    asset = artifact(entry, target)

    assert observed_archive(asset.name) is asset.archive, f'{entry} declares {asset.archive} for {case_id(target)} and names {asset.name}'


@pytest.mark.parametrize(('entry', 'target'), CORPUS, ids=case_id)
def test_only_an_archive_of_several_files_says_which_one_to_take(entry: str, target: Target) -> None:
    """`path` is read for a tarball or a zip and ignored for the other two.

    An empty one resolves to the unpacked directory, which is not a file, so the
    install refuses with `ARCHIVE_INCOMPLETE`. A path set on a raw download or a
    gzip is the opposite failure and quieter: nothing reads it, so it is a claim
    about the archive that no install can contradict.
    """
    asset = artifact(entry, target)

    assert asset.name, f'{entry} named no asset for {case_id(target)}'
    if asset.archive in UNPACKED:
        assert asset.path, f'{entry} unpacks {asset.name} and does not say which file to take'
    else:
        assert asset.path == '', f'{entry} is a {asset.archive} download and declares path {asset.path!r}, which nothing reads'


@pytest.mark.parametrize(('entry', 'target'), CORPUS, ids=case_id)
def test_everything_taken_out_of_an_archive_is_addressed_from_inside_it(entry: str, target: Target) -> None:
    """One archive is unpacked once, and every member is named relative to that.

    A unit or an extra that walks out of the binary's own directory is a member
    the archive does not hold, which `_place` reports as `ARCHIVE_INCOMPLETE` for
    the unit and passes over in silence for the extra.
    """
    asset = artifact(entry, target)

    if asset.unit:
        assert asset.unit.split('/')[0] == asset.path.split('/')[0], f'{entry} takes {asset.unit} from outside {asset.path}'
    for extra in asset.extras:
        assert PurePosixPath(extra).parent == PurePosixPath(asset.path).parent, f'{entry} places {extra}, which is not beside {asset.path}'
    if asset.tree:
        assert '/' in asset.path, f'{entry} installs a tree and its binary {asset.path!r} is not inside one'


@pytest.mark.parametrize('target', [target for target in TARGETS if target.is_darwin], ids=case_id)
@pytest.mark.parametrize('entry', ENTRIES)
def test_a_systemd_unit_is_declared_only_where_systemd_runs(entry: str, target: Target) -> None:
    """syncthing's macOS zip carries the same `etc/linux-systemd/` directory its
    tarball does, where it means nothing. A unit declared there is installed under
    `$XDG_CONFIG_HOME/systemd/user` on a Mac, and `AGENTS` is what supervises one
    there instead."""
    asset = artifact(entry, target)

    assert asset.name, f'{entry} named no asset for {case_id(target)}'
    assert asset.unit == '', f'{entry} declares the unit {asset.unit} for {case_id(target)}'


@pytest.mark.parametrize('entry', ENTRIES)
def test_two_targets_that_fetch_one_file_unpack_it_the_same_way(entry: str) -> None:
    """One download cannot hold two layouts.

    This is what a half-lost branch looks like from the inside: a function whose
    name stopped varying with the target while its `path` kept doing so installs
    the wrong file out of the right archive, and every other rule here still
    passes.
    """
    seen: dict[str, tuple[Target, ReleaseArtifact]] = {}
    for target in TARGETS:
        asset = artifact(entry, target)
        first, expected = seen.setdefault(asset.name, (target, asset))
        assert asset == expected, f'{entry} fetches {asset.name} for both {case_id(first)} and {case_id(target)}, and unpacks it two ways'


# ─────────────────────────────────────────────────────────────────────────────
# That every target branch is still reachable
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('arch', tuple(Arch))
@pytest.mark.parametrize('entry', ON_BOTH_SYSTEMS)
def test_a_mac_and_a_linux_box_never_fetch_the_same_file(entry: str, arch: Arch) -> None:
    """Scoped to the entries some manifest installs on both, which is what makes
    it a rule rather than a list of exceptions: atuin is a linux triple on both
    branches and win32yank is one Windows binary, and neither is asked for on a
    Mac."""
    darwin = artifact(entry, Target(OSFamily.DARWIN, arch))
    linux = artifact(entry, Target(OSFamily.LINUX, arch))

    assert darwin.name != linux.name, f'{entry} fetches {darwin.name} on {arch} for both systems'


@pytest.mark.parametrize('entry', ON_DARWIN)
def test_the_two_mac_architectures_never_fetch_the_same_file(entry: str) -> None:
    """The branch nothing else can see.

    macOS is the one system here serving two architectures, so an arm branch that
    stops being reachable is invisible from whichever Mac runs a check — the Intel
    binary downloads, runs under Rosetta, and reports itself installed. That fusion
    is what `Target` exists to break, and this is the assertion that spends it.
    """
    arm = artifact(entry, Target(OSFamily.DARWIN, Arch.ARM64))
    intel = artifact(entry, Target(OSFamily.DARWIN, Arch.X86_64))

    if entry in UNIVERSAL_ON_DARWIN:
        assert arm == intel, f'{entry} is exempt because it {UNIVERSAL_ON_DARWIN[entry]}, so it owes one artifact rather than two spellings'
        return
    assert arm.name != intel.name, f'{entry} fetches {arm.name} on both Apple Silicon and Intel'


def test_a_windows_machine_asks_for_none_of_these_because_windows_is_linux_here() -> None:
    """Not one function branches on windows, so a name borrowed for a Windows box
    fetches a Linux binary and reports it installed.

    Both halves are asserted together because either alone reads as a preference:
    what the code does with a windows target is the hazard, and what the manifests
    do about it is the only thing keeping the hazard off a machine.
    """
    for arch in Arch:
        for entry in ENTRIES:
            windows = artifact(entry, Target(OSFamily.WINDOWS, arch))
            assert windows == artifact(entry, Target(OSFamily.LINUX, arch)), f'{entry} names something of its own for windows'

    asking = sorted(entry for entry, families in ASKED_FOR.items() if OSFamily.WINDOWS in families)

    assert not asking, f'{", ".join(asking)} is declared on a windows machine, which would fetch the linux binary'


# ─────────────────────────────────────────────────────────────────────────────
# The tag, and the URL built from it
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('target', TARGETS, ids=case_id)
@pytest.mark.parametrize('entry', PREFIXED_TAGS)
def test_a_prefixed_tag_reaches_the_asset_name_as_a_bare_version(entry: str, target: Target) -> None:
    """The four data CLIs are nested Go modules whose repos release an app too, so
    their tag carries a `cli/` the asset name must not.

    Asserted as an invariance rather than against a spelling: whatever the name
    turns out to be, `cli/v1.2.3` and `1.2.3` have to produce the same artifact,
    which is true only if the prefix and the `v` are both gone.
    """
    prefix = DECLARED[entry].release_tag_prefix
    prefixed = providers.ASSETS[entry](f'{prefix}v1.2.3', target)

    assert prefixed == providers.ASSETS[entry]('1.2.3', target), f'{entry} carries its {prefix!r} tag into {prefixed.name}'


@pytest.mark.parametrize('entry', ENTRIES)
def test_the_download_url_carries_the_repo_the_tag_and_the_asset(entry: str) -> None:
    """Read back with the product's own parser rather than compared against a
    string this test also built.

    `parse_release_url` is what `github_release.download_asset` falls back through
    to the asset-id endpoint a private repo needs, so a URL it cannot read is one
    the two private CLIs cannot be downloaded from at all — and a tag with a slash
    in it is the shape that tests whether it can.

    One target, because the name is what varies and every target's name is already
    held to being a single path segment above.
    """
    declared = DECLARED[entry]
    tag = tag_for(entry)
    asset = artifact(entry, Target(OSFamily.LINUX, Arch.X86_64))

    url = providers.asset_url(declared.repo, tag, asset)

    assert github_release.parse_release_url(url) == (declared.repo, tag)
    assert url.rsplit('/', 1)[-1] == asset.name


class TestCorpus:
    """Guards that the tables above are not vacuously green."""

    def test_every_release_is_asked_about_on_both_architectures_of_both_systems(self) -> None:
        assert {entry for entry, _ in CORPUS} == set(providers.ASSETS)
        assert {(target.os_family, target.arch) for _, target in CORPUS} == {
            (OSFamily.DARWIN, Arch.ARM64),
            (OSFamily.DARWIN, Arch.X86_64),
            (OSFamily.LINUX, Arch.ARM64),
            (OSFamily.LINUX, Arch.X86_64),
        }

    def test_the_distinctness_rules_have_a_corpus_derived_from_the_manifests(self) -> None:
        """Both are parametrized off what machines ask for, and pytest collects
        nothing at all from an empty list — a derivation that started answering
        nothing would take both rules with it and report green."""
        assert ON_BOTH_SYSTEMS and ON_DARWIN
        assert set(ON_BOTH_SYSTEMS) <= set(providers.ASSETS) and set(ON_DARWIN) <= set(providers.ASSETS)

    def test_a_release_declares_a_systemd_unit_for_the_linux_rule_to_be_about(self) -> None:
        """The mac rule above asserts an absence, which an empty `unit` on every
        entry would satisfy for the wrong reason."""
        linux = Target(OSFamily.LINUX, Arch.X86_64)

        assert [entry for entry in ENTRIES if artifact(entry, linux).unit]

    def test_a_release_ships_extras_and_one_installs_as_a_tree(self) -> None:
        """Both are conditionals inside the placement rule, and neither is reached
        if the table stops carrying an entry that uses them."""
        linux = Target(OSFamily.LINUX, Arch.X86_64)

        assert [entry for entry in ENTRIES if artifact(entry, linux).extras]
        assert [entry for entry in ENTRIES if artifact(entry, linux).tree]

    def test_every_entry_exempted_from_the_architecture_rule_is_still_declared(self) -> None:
        """A renamed tool leaves its exemption behind, and an exemption naming
        nothing is one nobody is going to read again."""
        assert set(UNIVERSAL_ON_DARWIN) <= set(providers.ASSETS)
