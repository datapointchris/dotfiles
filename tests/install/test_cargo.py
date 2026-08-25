"""Which source a Rust CLI comes from, and what happens when it cannot be reached.

The whole of this provider is that decision, so the seam is `effects.run` — cargo
binstall either answers or it does not — and the bundle is a real directory with a
real manifest and a real tarball in it, because "does the bundle carry this" is a
filesystem question and stubbing it would assert nothing.

The naming round trip that `test_cargo_tools_sh.py` parametrized over every entry
is gone with the glob it existed for. The bundler now says which file it wrote and
the installer reads that row, so the two cannot disagree about a name; what is
still worth asserting is that the binary inside the archive is found under the name
the *declaration* gives it, which is the half a manifest cannot state.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles import providers
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import Kind
from dotfiles.providers import bundle
from dotfiles.providers import cargo

FD = catalog.CargoPackage.from_mapping({'name': 'fd-find', 'command': 'fd', 'github_repo': 'sharkdp/fd'})

REFUSED = 'ConnectError: certificate verify failed: unable to get local issuer certificate'

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
MACOS = Target(OSFamily.DARWIN, Arch.ARM64)

BINARY = b'#!/bin/sh\necho fd\n'

BINSTALL = ('cargo', 'binstall', '-y', 'fd-find')
"""The whole command, in one place, so every test asserting binstall was the
source and the one asserting when `--force` joins it cannot drift apart."""


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    (root / '.cargo' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(root))
    return root


@pytest.fixture
def staged(tmp_path, monkeypatch) -> Path:
    """An offline bundle with nothing in it yet."""
    root = tmp_path / 'staged'
    staging = root / 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
    (staging / cargo.BUNDLE_BINARIES).mkdir(parents=True)
    (staging / providers.MANIFEST).write_text('')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(root))
    return staging


@pytest.fixture
def crates(upstream):
    """`cargo binstall`, answering however this test says crates.io behaved."""
    return upstream


@pytest.fixture
def ready(monkeypatch, home):
    """cargo-binstall already on PATH, which is the state after the first package.

    Patched at `shutil.which` inside the provider rather than by writing a file
    into a fake PATH, because the precondition asks two different questions of
    PATH — `cargo-binstall` and `cargo` — and only the first is being answered.
    """
    monkeypatch.setattr(cargo.shutil, 'which', lambda name: f'/somewhere/{name}' if name == 'cargo-binstall' else None)


def stage(staging: Path, filename: str, *, name: str = 'fd-find', version: str = 'v10.4.2', binary: str = 'fd', at: str = '') -> Path:
    """A real archive and the manifest row that names it, as the bundler writes them."""
    payload = staging / 'build' / (at or binary)
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(BINARY)

    archive = staging / cargo.BUNDLE_BINARIES / filename
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(payload, arcname=at or binary)

    manifest = staging / bundle.MANIFEST
    rows = manifest.read_text() if manifest.is_file() else '# Dotfiles Offline Bundle\n'
    manifest.write_text(f'{rows}cargo|{name}|{version}|{filename}\n')
    return archive


# ─────────────────────────────────────────────────────────────────────────────
# Which source, and why
# ─────────────────────────────────────────────────────────────────────────────


def test_an_online_run_takes_binstall_even_when_a_bundle_is_present(home, staged, ready, crates) -> None:
    """`cargo binstall` is the upgrade, and the bundle is a snapshot of whatever was
    current when it was built — so a run with a network should move past it. With
    currency on these entries, preferring the bundle would have `apply` repair a
    STALE tool by reinstalling the same stale bytes forever."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    reached = crates()

    result = cargo.install(FD, LINUX, offline=False, floor='')

    assert result.ok
    assert reached.calls == [BINSTALL]


def test_a_binary_the_bundle_left_behind_is_installed_over_with_force(home, staged, ready, crates) -> None:
    """binstall's last strategy is `cargo install`, which refuses to overwrite a
    binary it does not own — the state `place` leaves, because it copies the file in
    and writes no `.crates.toml` row. A firewalled machine reaches that strategy for
    every crate, so without `--force` every crate it once restored from a bundle
    fails with `binary ... already exists in destination`."""
    left = home / '.cargo' / 'bin' / 'fd'
    left.write_bytes(BINARY)
    reached = crates()

    cargo.install(FD, LINUX, offline=False, floor='')

    assert reached.calls == [('cargo', 'binstall', '-y', '--force', 'fd-find')]


def test_a_binary_cargo_owns_is_installed_over_without_force(home, staged, ready, crates) -> None:
    """`--force` also defeats binstall's already-installed short-circuit, so passing
    it always would re-download every crate on every apply. The receipt is what
    separates the two cases."""
    left = home / '.cargo' / 'bin' / 'fd'
    left.write_bytes(BINARY)
    (home / '.cargo' / '.crates.toml').write_text('[v1]\n"fd-find 10.4.2 (registry+https://x)" = ["fd"]\n')
    reached = crates()

    cargo.install(FD, LINUX, offline=False, floor='')

    assert reached.calls == [BINSTALL]


def test_a_first_install_has_nothing_to_force_over(home, staged, ready, crates) -> None:
    reached = crates()

    cargo.install(FD, LINUX, offline=False, floor='')

    assert reached.calls == [BINSTALL]


def test_the_receipt_is_read_by_binary_name_not_by_crate_name(home, staged, ready) -> None:
    """A crate installs binaries under names of its own choosing, which is the split
    `entry.command` exists for — the receipt's key is `fd-find` and its value is
    `fd`, and only the value answers who owns the file on disk."""
    (home / '.cargo' / '.crates.toml').write_text('[v1]\n"fd-find 10.4.2 (registry+https://x)" = ["fd"]\n')

    assert cargo.cargo_owns('fd')
    assert not cargo.cargo_owns('fd-find')


def test_an_unreadable_receipt_is_not_read_as_ownership(home, staged, ready) -> None:
    """Claiming ownership nothing can demonstrate is what leaves `cargo install`
    refusing with no way out."""
    (home / '.cargo' / '.crates.toml').write_text('this is not toml {{{')

    assert not cargo.cargo_owns('fd')


def test_binstall_is_streamed_so_a_source_build_is_visible(home, staged, ready, crates) -> None:
    """binstall's last strategy is a source build, and a crate with no prebuilt
    binary for this target reaches it — `oxker` and `broot` both do on macOS.
    That build takes as long as the crate takes. Buffered, it reads as a deadlock
    — the failure `Output.STREAM` exists to prevent.

    Asserted as an absence, because `effects.run` owns the default and
    `test_provider_seams.py` pins it there. Restating `Output.STREAM` here would
    read as green if that signature were flipped, which is the state this name
    claims to hold. The call is selected by its argv rather than by position:
    `binstall()` installs cargo-binstall itself when it is missing, and that call
    takes index 0 on a box that has never run one.
    """
    reached = crates()

    cargo.install(FD, LINUX, offline=False, floor='')

    passed = next(kw for argv, kw in zip(reached.calls, reached.kwargs, strict=True) if argv[:2] == ('cargo', 'binstall'))
    assert 'output' not in passed


def test_an_offline_run_takes_the_bundle_without_trying_crates_io(home, staged, ready, crates) -> None:
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    reached = crates()

    result = cargo.install(FD, LINUX, offline=True, floor='')

    assert result.ok
    assert reached.calls == []
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_an_unreachable_crates_io_falls_back_to_the_bundle(home, staged, ready, crates) -> None:
    """On a firewalled machine crates.io is never reachable, and without this every
    Rust tool stays at the version the machine was first built with while a current
    bundle sits unused on disk."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates(reachable=False)

    result = cargo.install(FD, LINUX, offline=False, floor='')

    assert result.ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_a_bundle_no_newer_than_what_is_installed_is_not_written_again(home, staged, ready, crates) -> None:
    """The write would produce a byte-identical binary, `apply` would report a change
    it did not make, and the next plan would find the row behind upstream again. A
    bundle a week older than crates.io on a firewalled machine is that state, and it
    repeats for as long as both stay true."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates(reachable=False, said='could not GET the release asset: timeout')

    result = cargo.install(FD, LINUX, offline=False, floor='10.4.2')

    assert not result.ok
    assert result.kind is Kind.BUNDLE_BEHIND
    assert not (home / '.cargo' / 'bin' / 'fd').exists()
    assert '10.4.2' in result.detail
    assert 'timeout' in result.detail, 'the transport error is the half a person acts on'


def test_a_bundle_ahead_of_what_is_installed_still_rescues_a_failed_binstall(home, staged, ready, crates) -> None:
    """The floor refuses a bundle that repairs nothing, never one that repairs
    something — a firewalled machine with a fresh bundle is the case the fallback
    exists for."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates(reachable=False)

    result = cargo.install(FD, LINUX, offline=False, floor='10.3.0')

    assert result.ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_a_bundle_below_what_is_installed_is_refused_too(home, staged, ready, crates) -> None:
    """The guard covers equal *and* below, and below is the aged-out bundle this is
    named for. Written against `exactly` rather than `exceeds`, every other case
    here stays green while a week-old bundle overwrites a newer binary with an
    older one."""
    stage(staged, 'fd-v10.3.0-x86_64-unknown-linux-gnu.tar.gz', version='v10.3.0')
    crates(reachable=False)

    result = cargo.install(FD, LINUX, offline=False, floor='10.4.2')

    assert not result.ok
    assert result.kind is Kind.BUNDLE_BEHIND
    assert not (home / '.cargo' / 'bin' / 'fd').exists()


@pytest.mark.parametrize('unrankable', ['', 'v10', '2024-11-26', 'nightly'])
def test_a_staged_version_that_cannot_be_ranked_does_not_lose_the_comparison(home, staged, ready, crates, unrankable) -> None:
    """`versions.exceeds` answers False for anything it cannot parse, so testing the
    two versions for emptiness reads "unreadable" as "not newer". `create_bundle`
    records whatever tag upstream published and that shape is not this repo's to
    constrain, so an unrankable row is one nothing measured — which is a reason to
    install it rather than to refuse the only source a firewalled machine has."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz', version=unrankable)
    crates(reachable=False)

    assert cargo.install(FD, LINUX, offline=False, floor='10.4.2').ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_a_failure_that_is_not_the_install_command_keeps_its_own_kind(home, staged, ready, crates, monkeypatch) -> None:
    """`binstall()` answers PREREQUISITE_MISSING where there is no cargo to build
    cargo-binstall with. That is a fault in the machine which outranks the bundle's
    age, and answering BUNDLE_BEHIND would send the reader to rebuild a bundle when
    the machine needs a toolchain."""
    monkeypatch.setattr(cargo.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(effects, 'fetch', lambda *_args, **_kwargs: github_release.Fetched(False, REFUSED))
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates()

    result = cargo.install(FD, LINUX, offline=False, floor='10.4.2')

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'no cargo' in result.detail


def test_the_refusal_names_the_command_that_repairs_it(home, staged, ready, crates) -> None:
    """`Outcome.from_result` drops `kind` and `advice_for` answers '' for a STALE
    row, so the detail is the only channel the machine has for a remedy."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates(reachable=False)

    result = cargo.install(FD, LINUX, offline=False, floor='10.4.2')

    assert 'dotfiles bundle download' in result.detail


def test_an_offline_run_ignores_the_version_floor(home, staged, ready, crates) -> None:
    """Offline, the bundle *is* what upstream published — `bundle.published` answers
    currency from the same manifest — so nothing can be ahead of it, and a floor
    would only refuse the one source there is."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates()

    assert cargo.install(FD, LINUX, offline=True, floor='10.4.2').ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_an_unreachable_crates_io_with_no_bundle_reports_what_binstall_said(home, staged, ready, crates) -> None:
    crates(reachable=False, said='error: could not resolve fd-find: dns error')

    result = cargo.install(FD, LINUX, offline=False, floor='')

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'dns error' in result.detail


def test_offline_with_nothing_staged_says_where_it_looked(home, staged, ready, crates) -> None:
    crates()

    result = cargo.install(FD, LINUX, offline=True, floor='')

    assert not result.ok
    assert result.kind is Kind.NOT_IN_BUNDLE
    assert str(paths.staging_dir()) in result.detail, 'a stack has no one bundle directory to name'


def test_a_manifest_row_naming_a_file_the_bundle_lacks_is_a_miss(home, staged, ready, crates) -> None:
    """Half a bundle — an interrupted extraction, a hand-pruned directory — reads as
    no bundle rather than as a failure, so an online run still installs."""
    (staged / bundle.MANIFEST).write_text('cargo|fd-find|v10.4.2|fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz\n')
    reached = crates()

    assert cargo.install(FD, LINUX, offline=False, floor='').ok
    assert reached.calls == [BINSTALL]


# ─────────────────────────────────────────────────────────────────────────────
# Getting the binary out of what the bundle staged
# ─────────────────────────────────────────────────────────────────────────────


def test_the_binary_is_found_by_the_name_the_declaration_gives_it(home, staged, ready, crates) -> None:
    """`command` is the override for a crate whose binary is named differently, and
    it is the crate name that keys the manifest — so neither half has to know the
    other's spelling."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates(reachable=False)

    assert cargo.install(FD, LINUX, offline=False, floor='').ok
    assert (home / '.cargo' / 'bin' / 'fd').is_file()
    assert not (home / '.cargo' / 'bin' / 'fd-find').exists()


def test_a_binary_nested_in_the_archive_is_found(home, staged, ready, crates) -> None:
    """Most projects tar a directory named for the version and target, with the
    binary inside it; a few tar the bare binary. Which one is upstream's choice."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz', at='fd-v10.4.2-x86_64-unknown-linux-gnu/fd')
    crates(reachable=False)

    assert cargo.install(FD, LINUX, offline=False, floor='').ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


def test_an_archive_without_the_binary_says_so_rather_than_falling_through(home, staged, ready, crates) -> None:
    """A staged archive that will not yield its binary is a broken bundle, not an
    absent one — and reporting it as absent would hide the only symptom."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz', binary='something-else')
    crates(reachable=False)

    result = cargo.install(FD, LINUX, offline=True, floor='')

    assert not result.ok
    assert result.kind is Kind.ARCHIVE_INCOMPLETE
    assert 'carries no fd' in result.detail


def test_a_bundled_binary_replaces_one_that_is_currently_running(home, staged, ready, crates) -> None:
    """A plain copy over a running binary fails with "text file busy"."""
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    running = home / '.cargo' / 'bin' / 'fd'
    running.write_bytes(b'#!/bin/sh\necho old\n')
    running.chmod(0o755)
    crates(reachable=False)

    assert cargo.install(FD, LINUX, offline=False, floor='').ok
    assert running.read_bytes() == BINARY
    assert not running.with_name('fd.new').exists()


# ─────────────────────────────────────────────────────────────────────────────
# The precondition
# ─────────────────────────────────────────────────────────────────────────────


def test_a_present_cargo_binstall_is_not_installed_again(home, staged, ready, crates) -> None:
    reached = crates()

    assert cargo.binstall(LINUX, offline=False).ok
    assert reached.calls == []


def test_offline_cannot_install_the_precondition_and_says_which_repo(home, staged, crates, monkeypatch) -> None:
    monkeypatch.setattr(cargo.shutil, 'which', lambda _name: None)
    crates()

    result = cargo.binstall(LINUX, offline=True)

    assert not result.ok
    assert result.kind is Kind.NOT_IN_BUNDLE
    assert cargo.BINSTALL_REPO in result.detail


def test_the_precondition_builds_from_source_when_the_release_cannot_be_had(home, staged, crates, monkeypatch) -> None:
    """The source build is the only path that works on the work box, where release
    asset downloads are blocked but crates.io is reachable."""
    monkeypatch.setattr(cargo.shutil, 'which', lambda name: None if name == 'cargo-binstall' else '/usr/bin/cargo')
    monkeypatch.setattr(effects, 'fetch', lambda *_args, **_kwargs: github_release.Fetched(False, REFUSED))
    reached = crates()

    result = cargo.binstall(LINUX, offline=False)

    assert result.ok
    assert reached.calls == [('cargo', 'install', 'cargo-binstall')]


def test_no_cargo_and_no_release_reports_both_halves(home, staged, crates, monkeypatch) -> None:
    monkeypatch.setattr(cargo.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(effects, 'fetch', lambda *_args, **_kwargs: github_release.Fetched(False, REFUSED))
    crates()

    result = cargo.binstall(LINUX, offline=False)

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'could not download' in result.detail
    assert REFUSED in result.detail, 'a bare "could not download" is what sent a TLS block to the wrong diagnosis'


def test_a_package_still_reaches_the_bundle_when_the_precondition_fails(home, staged, crates, monkeypatch) -> None:
    """The precondition failing is not a reason to skip a tool the bundle already
    carries — which is the whole install on a machine with no working network."""
    monkeypatch.setattr(cargo.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(effects, 'fetch', lambda *_args, **_kwargs: github_release.Fetched(False, REFUSED))
    stage(staged, 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz')
    crates()

    assert cargo.install(FD, LINUX, offline=False, floor='').ok
    assert (home / '.cargo' / 'bin' / 'fd').read_bytes() == BINARY


# ─────────────────────────────────────────────────────────────────────────────
# Naming
# ─────────────────────────────────────────────────────────────────────────────


def test_the_triple_names_the_platform_a_release_asset_is_built_for() -> None:
    assert cargo.triple(LINUX) == 'x86_64-unknown-linux-gnu'
    assert cargo.triple(MACOS) == 'aarch64-apple-darwin'
    assert cargo.triple(Target(OSFamily.DARWIN, Arch.X86_64)) == 'x86_64-apple-darwin'
    assert cargo.triple(Target(OSFamily.LINUX, Arch.ARM64)) == 'aarch64-unknown-linux-gnu'
