"""The nine vendors that ship themselves: what each one decides, and when.

No network and no subprocesses. What a custom installer *is* is a decision about
whether to act and a handful of downloads and commands, so the seam is
`effects.fetch` and `effects.run` — recorded rather than performed, which makes
the interesting assertion "what did it decide to do" rather than "did it work".

Real `packages.yml` entries throughout, unlike `test_ghrelease.py`, which
registers synthetic assets. There is nothing generic here to exercise: the
function *is* the tool, keyed by the name it is declared under, so a synthetic
entry would test a function that does not exist.
"""

from __future__ import annotations

import dataclasses
import io
import zipfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import evidence
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import providers
from dotfiles import resolve
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.effects import Completed
from dotfiles.providers import Kind
from dotfiles.providers import custom

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
DARWIN = Target(OSFamily.DARWIN, Arch.ARM64)

SCRIPT = b'#!/bin/sh\necho installed\n'


@pytest.fixture(scope='module')
def declared() -> catalog.Catalog:
    return catalog.load()


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    (root / '.local' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(root))
    monkeypatch.setenv('PATH', str(root / '.local' / 'bin'))
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'staged'
    staged = root / 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
    (staged / 'scripts').mkdir(parents=True)
    (staged / providers.MANIFEST).write_text('')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(root))
    return staged


class Runs:
    """Every command an installer would have started, and what it was told back.

    Answers are matched against any part of the argv, so a test names the thing
    it cares about (`'update'`, `'install.sh'`) rather than reproducing the whole
    command line the function happens to build.

    A successful `git clone` creates its destination and a `bash <script>` has its
    body read, both before returning. Everything an installer stages sits in a
    temporary directory it deletes on the way out, so a recorder that only kept
    the argv would leave every assertion about *what* was run unanswerable.
    """

    def __init__(self, **answers: Completed) -> None:
        self.answers = answers
        self.calls: list[tuple[str, ...]] = []
        self.scripts: list[bytes] = []

    def __call__(self, command, *, cwd=None, env=None, output=effects.Output.STREAM) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        answer = next((completed for key, completed in self.answers.items() if any(key in part for part in argv)), Completed(argv, 0, ''))
        # A fake naming only what a command printed means it printed it on stdout.
        # A real `Output.QUIET` run fills both fields and every parser reads
        # `stdout`, so without this a fixture would model an answer no subprocess
        # can produce — and the gpg fingerprint read would find nothing.
        answer = dataclasses.replace(answer, stdout=answer.stdout or answer.transcript)

        if argv[0] == 'bash' and Path(argv[1]).is_file():
            self.scripts.append(Path(argv[1]).read_bytes())
        if answer.ok and argv[:2] == ('git', 'clone'):
            Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        return answer

    def ran(self, fragment: str) -> bool:
        return any(fragment in part for argv in self.calls for part in argv)


class Fetches:
    """Every URL an installer would have downloaded, with a body per URL."""

    def __init__(
        self,
        bodies: dict[str, bytes] | None = None,
        refuse: tuple[str, ...] = (),
        reason: str = 'ConnectError: certificate verify failed: unable to get local issuer certificate',
    ) -> None:
        self.bodies = bodies or {}
        self.refuse = refuse
        self.reason = reason
        self.urls: list[str] = []

    def __call__(self, url: str, destination: Path, **_kwargs) -> github_release.Fetched:
        """`Fetched`, not a bool, because that is what `effects.fetch` answers.

        A double returning a bare `False` would still read as a failure at every
        `if not fetch(...)`, so this is not about the branch — it is about `.reason`,
        which the providers now quote into their own messages. A refusal carries the
        text a TLS-intercepting proxy would produce, so a test can assert the cause
        survives the trip rather than only that the install failed.
        """
        self.urls.append(url)
        if any(part in url for part in self.refuse):
            return github_release.Fetched(False, self.reason)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.bodies.get(url, SCRIPT))
        return github_release.Fetched(True)


@pytest.fixture
def effected(monkeypatch):
    """Install the two recorders, defaulting to "everything worked, silently"."""

    def install(runs: Runs | None = None, fetches: Fetches | None = None) -> tuple[Runs, Fetches]:
        runs, fetches = runs or Runs(), fetches or Fetches()
        monkeypatch.setattr(effects, 'run', runs)
        monkeypatch.setattr(effects, 'fetch', fetches)
        return runs, fetches

    return install


def stub_binary(home: Path, name: str) -> Path:
    binary = home / '.local' / 'bin' / name
    binary.write_bytes(SCRIPT)
    binary.chmod(0o755)
    return binary


def reports(monkeypatch, **versions: str | None) -> None:
    """What each executable would say if asked its version."""
    monkeypatch.setattr(evidence, 'reported_version', lambda executable: versions.get(executable))


def latest(monkeypatch, tag: str | None) -> None:
    monkeypatch.setattr(github_release, 'latest_version', lambda repo, prefix='': tag)


# ─────────────────────────────────────────────────────────────────────────────
# The registry itself
# ─────────────────────────────────────────────────────────────────────────────


class TestCorpus:
    """The half `validate.py` cannot ask, because it runs against a synthetic tree."""

    def test_every_declared_installer_has_a_function(self, declared):
        assert {entry.name for entry in declared.section('custom_installers')} <= set(custom.INSTALLERS)

    def test_no_function_names_a_tool_nothing_declares(self, declared):
        """The reverse direction. A function for a deleted entry is dead code that
        reads as coverage, which is how `install_script` fields came to name
        scripts half the entries no longer had."""
        assert set(custom.INSTALLERS) <= {entry.name for entry in declared.section('custom_installers')}

    def test_every_installer_says_what_it_reaches_for(self):
        """A tool absent from SOURCES probes nothing and reports no block, which is
        indistinguishable from a reachable host."""
        assert set(custom.SOURCES) == set(custom.INSTALLERS)

    def test_an_undeclared_name_is_refused_rather_than_crashing(self, declared):
        made_up = catalog.CustomInstaller(name='nosuchtool', description='invented')

        result = custom.install(made_up, LINUX)

        assert not result.ok
        assert result.kind is Kind.DECLARATION_INVALID


class TestSources:
    """What a connectivity probe is told to try."""

    def test_a_personal_cli_names_both_its_script_host_and_its_repo(self, declared):
        found = custom.sources(declared.find('custom_installers', 'theme'), LINUX)

        assert [source.reach for source in found] == [custom.Reach.DOWNLOAD, custom.Reach.CLONE]
        assert 'raw.githubusercontent.com' in found[0].url
        assert found[1].url.endswith('theme.git')

    def test_bats_names_all_three_repos(self, declared):
        found = custom.sources(declared.find('custom_installers', 'bats'), LINUX)

        assert [source.reach for source in found] == [custom.Reach.CLONE] * 3
        assert {'bats-core', 'bats-support', 'bats-assert'} == {source.url.rsplit('/', 1)[1].removesuffix('.git') for source in found}

    def test_the_zip_is_named_per_architecture(self, declared):
        entry = declared.find('custom_installers', 'awscli')

        assert custom.sources(entry, LINUX)[0].url.endswith('awscli-exe-linux-x86_64.zip')
        assert custom.sources(entry, Target(OSFamily.LINUX, Arch.ARM64))[0].url.endswith('awscli-exe-linux-aarch64.zip')

    @pytest.mark.parametrize('tool', ['awscli', 'mount-s3'])
    def test_a_platform_that_installs_it_elsewhere_names_nothing(self, declared, tool):
        """Not a failure to look. awscli comes from Homebrew on a Mac and mount-s3
        has no macOS build at all, so probing either would report a block against
        a host the machine was never going to contact."""
        assert custom.sources(declared.find('custom_installers', tool), DARWIN) == ()

    def test_mount_s3_probes_the_tarball_and_never_the_bucket_root(self, declared):
        """Listing the root 403s, so probing it reports a block that is really S3
        refusing to enumerate."""
        found = custom.sources(declared.find('custom_installers', 'mount-s3'), LINUX)

        assert [source.url.rsplit('/', 1)[1] for source in found] == ['mount-s3.tar.gz', 'KEYS']

    def test_terraform_ls_probes_a_path_that_needs_no_version(self, declared):
        """The asset name carries a version the release API has not been asked for
        yet, and a probe that needed one would fail for the wrong reason."""
        found = custom.sources(declared.find('custom_installers', 'terraform-ls'), LINUX)

        assert found[0].url == 'https://releases.hashicorp.com/terraform-ls/'


# ─────────────────────────────────────────────────────────────────────────────
# The personal CLIs
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckoutTools:
    """theme, font and zmk: cloned by a vendor script, updated by themselves."""

    def test_an_absent_checkout_runs_the_vendor_script(self, declared, home, bundle, effected):
        entry = declared.find('custom_installers', 'theme')
        runs, fetches = effected()

        result = custom.install(entry, LINUX)

        assert result.ok, result.detail
        assert fetches.urls == [entry.install_url]
        assert runs.ran('install.sh')

    def test_a_live_checkout_delegates_to_the_tool_rather_than_reinstalling(self, declared, home, bundle, effected):
        """Re-running the install script over a live checkout would be a second,
        worse implementation of the `update` the tool already ships."""
        (home / '.local' / 'share' / 'theme' / '.git').mkdir(parents=True)
        stub_binary(home, 'theme')
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'theme'), LINUX)

        assert result.ok, result.detail
        assert runs.calls == [('theme', 'update')]
        assert fetches.urls == []

    def test_a_failing_update_propagates_rather_than_being_swallowed(self, declared, home, bundle, effected):
        """Matching on the tool's output to infer a result is how `theme updated`
        came to be printed on every run, and how a real failure went unreported."""
        (home / '.local' / 'share' / 'font' / '.git').mkdir(parents=True)
        stub_binary(home, 'font')
        effected(Runs(update=Completed(('font', 'update'), 1, 'could not fetch')))

        result = custom.install(declared.find('custom_installers', 'font'), LINUX)

        assert not result.ok
        assert result.kind is Kind.COMMAND_FAILED
        assert 'exited 1' in result.detail

    def test_a_delegated_update_adds_no_verdict_of_its_own(self, declared, home, bundle, effected):
        """`font already at latest` with `font updated` printed under it is what the
        bash did, and the second line is both redundant and false."""
        (home / '.local' / 'share' / 'font' / '.git').mkdir(parents=True)
        stub_binary(home, 'font')
        effected()

        result = custom.install(declared.find('custom_installers', 'font'), LINUX)

        assert result.kind is Kind.APPLIED
        assert result.detail == ''

    def test_a_checkout_whose_binary_vanished_is_drift_not_success(self, declared, home, bundle, effected):
        (home / '.local' / 'share' / 'zmk' / '.git').mkdir(parents=True)
        effected()

        result = custom.install(declared.find('custom_installers', 'zmk'), LINUX)

        assert not result.ok
        assert result.kind is Kind.NOT_ON_PATH

    def test_offline_leaves_an_installed_tool_alone(self, declared, home, bundle, effected):
        """Every one of these updates over the network, so offline has nothing to
        compare against and nothing to fetch. Failing the phase would report a
        machine as broken for being exactly what its bundle made it."""
        (home / '.local' / 'share' / 'theme' / '.git').mkdir(parents=True)
        stub_binary(home, 'theme')
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'theme'), LINUX, offline=True)

        assert result.ok
        assert result.kind is Kind.UNCHANGED
        assert runs.calls == [] and fetches.urls == []

    def test_offline_with_nothing_installed_says_what_the_bundle_lacks(self, declared, home, bundle, effected):
        runs, _ = effected()

        result = custom.install(declared.find('custom_installers', 'theme'), LINUX, offline=True)

        assert not result.ok
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert str(paths.staging_dir()) in result.detail
        assert runs.calls == []

    def test_a_bundled_script_is_preferred_over_the_network(self, declared, home, bundle, effected):
        """Served from an unversioned URL, so a machine restoring from a bundle has
        to run the script that bundle was built against."""
        (bundle / 'scripts' / 'theme-install.sh').write_bytes(b'#!/bin/sh\necho from-bundle\n')
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'theme'), LINUX, offline=True)

        assert result.ok, result.detail
        assert fetches.urls == []
        assert runs.scripts == [b'#!/bin/sh\necho from-bundle\n']


class TestBashselfupdate:
    def test_a_live_checkout_is_re_run_rather_than_skipped(self, declared, home, bundle, effected):
        """Its install script *is* its update — it re-checks-out onto the newest
        tag — and it is a sourced library, so there is no command to delegate to."""
        entry = declared.find('custom_installers', 'bashselfupdate')
        Path(entry.installed_path).expanduser().mkdir(parents=True)
        runs, fetches = effected()

        result = custom.install(entry, LINUX)

        assert result.ok, result.detail
        assert fetches.urls == [entry.install_url]
        assert runs.ran('install.sh')

    def test_its_evidence_is_the_checkout_and_not_a_binary(self, declared, home, bundle, effected):
        """Nothing lands on PATH, so `_confirm` would report it missing forever."""
        entry = declared.find('custom_installers', 'bashselfupdate')
        runs, _ = effected()

        result = custom.install(entry, LINUX)

        assert result.ok, result.detail
        assert not runs.ran('which')


class TestClaudeCode:
    def test_an_installed_claude_is_left_to_update_itself(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, claude='2.1.0 (Claude Code)')
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'claude-code'), LINUX)

        assert result.ok
        assert result.kind is Kind.UNCHANGED
        assert runs.calls == [] and fetches.urls == []

    def test_an_installer_refusing_because_claude_is_running_is_not_a_failure(self, declared, home, bundle, effected, monkeypatch):
        """On this machine Claude is always running, because the process asking for
        the install is Claude. The binary already there keeps working."""
        reports(monkeypatch, claude=None)
        effected(Runs(**{'install.sh': Completed(('bash',), 1, 'another process is currently installing Claude Code')}))

        result = custom.install(declared.find('custom_installers', 'claude-code'), LINUX)

        assert result.ok
        assert result.kind is Kind.UNCHANGED

    def test_any_other_failure_is_still_a_failure(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, claude=None)
        effected(Runs(**{'install.sh': Completed(('bash',), 1, 'disk full')}))

        result = custom.install(declared.find('custom_installers', 'claude-code'), LINUX)

        assert not result.ok
        assert result.kind is Kind.COMMAND_FAILED
        assert 'exited 1' in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# Vendors with their own distribution
# ─────────────────────────────────────────────────────────────────────────────


class TestAwscli:
    def test_macos_never_plans_it_at_all_because_homebrew_has_the_formula(self, declared):
        """Deferring inside the installer instead — a branch returning success
        having done nothing — is still a planned item, a measured row and a printed
        line on every run of a Mac with nothing wrong."""
        entry = declared.find('custom_installers', 'awscli')

        assert not resolve.available(entry, machines.load('macos-personal-workstation').coordinates)
        assert resolve.available(entry, machines.load('archlinux-personal-workstation').coordinates)

    def test_an_installed_aws_is_still_converged_because_presence_is_not_currency(self, declared, home, bundle, effected, monkeypatch):
        """Currency for awscli is the resource's, against `aws/aws-cli`'s tags, so
        reaching this function means the machine is behind it. Ending here on
        presence would make the entry unupgradable: the vendor's 73MB zip is the
        only other thing that knows what version it holds."""
        reports(monkeypatch, aws='aws-cli/2.36.18 Python/3.14.6')
        stub_binary(home, 'aws')
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, 'w') as archive:
            archive.writestr('aws/install', '#!/bin/sh\n')
        url = 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip'
        runs, _ = effected(fetches=Fetches({url: zipped.getvalue()}))

        result = custom.install(declared.find('custom_installers', 'awscli'), LINUX)

        assert result.ok, result.detail
        assert any('aws/install' in argv[0] for argv in runs.calls)

    def test_an_installed_aws_is_left_alone_offline(self, declared, home, bundle, effected, monkeypatch):
        """The one case that ends without asking: nothing staged to install from,
        and no network to fetch the vendor's zip."""
        reports(monkeypatch, aws='aws-cli/2.36.19 Python/3.14.6')
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'awscli'), LINUX, offline=True)

        assert result.ok
        assert fetches.urls == [] and runs.calls == []

    def test_an_absent_aws_offline_is_refused_rather_than_failing_the_run(self, declared, home, bundle, effected, monkeypatch):
        """Nothing stages the 73MB vendor zip, so an offline machine that never had
        awscli cannot get one. Refused, because a machine missing a tool its bundle
        was never built to carry is not a failed install."""
        reports(monkeypatch, aws=None)
        runs, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'awscli'), LINUX, offline=True)

        assert not result.ok
        assert result.refused
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert fetches.urls == [] and runs.calls == []

    def test_an_absent_aws_runs_the_vendor_installer_against_local_directories(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, aws=None)
        stub_binary(home, 'aws')
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, 'w') as archive:
            archive.writestr('aws/install', '#!/bin/sh\n')
        url = 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip'
        runs, _ = effected(fetches=Fetches({url: zipped.getvalue()}))

        result = custom.install(declared.find('custom_installers', 'awscli'), LINUX)

        assert result.ok, result.detail
        installed = next(argv for argv in runs.calls if 'aws/install' in argv[0])
        assert str(home / '.local' / 'aws-cli') in installed
        assert str(home / '.local' / 'bin') in installed
        assert '--update' in installed


class TestMountS3:
    def test_macos_has_no_build_to_install(self, declared, home, bundle, effected):
        _, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'mount-s3'), DARWIN)

        assert result.ok
        assert result.kind is Kind.UNSUPPORTED_HERE
        assert fetches.urls == []

    def test_an_unpinned_signing_key_refuses_the_install(self, declared, home, bundle, effected, monkeypatch):
        """The key is served from the same bucket as the tarball it signs, so
        importing whatever KEYS holds proves only that the bucket agrees with
        itself."""
        reports(monkeypatch, **{'mount-s3': None})
        monkeypatch.setattr(custom.shutil, 'which', lambda name: '/usr/bin/gpg' if name == 'gpg' else None)
        effected(Runs(**{'--list-keys': Completed(('gpg',), 0, 'fpr:::::::::DEADBEEF:\n')}))

        result = custom.install(declared.find('custom_installers', 'mount-s3'), LINUX)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'pinned fingerprints' in result.detail

    def test_a_bad_signature_refuses_the_install(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, **{'mount-s3': None})
        monkeypatch.setattr(custom.shutil, 'which', lambda name: '/usr/bin/gpg' if name == 'gpg' else None)
        effected(
            Runs(
                **{
                    '--list-keys': Completed(('gpg',), 0, f'fpr:::::::::{custom.MOUNT_S3_KEYS[0]}:\n'),
                    '--verify': Completed(('gpg',), 1, 'BAD signature'),
                }
            )
        )

        result = custom.install(declared.find('custom_installers', 'mount-s3'), LINUX)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'did not verify' in result.detail

    def test_no_gpg_warns_rather_than_refusing(self, declared, home, bundle, effected, monkeypatch, capsys):
        """A machine with no gnupg has not been shown a bad signature, it has been
        unable to look."""
        reports(monkeypatch, **{'mount-s3': None})
        tarball = _tarball({'bin/mount-s3': SCRIPT})
        url = 'https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.tar.gz'
        effected(fetches=Fetches({url: tarball}))

        result = custom.install(declared.find('custom_installers', 'mount-s3'), LINUX)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'mount-s3').read_bytes() == SCRIPT
        assert 'signature could not be checked' in capsys.readouterr().err


class TestTerraformLs:
    def test_offline_refuses_it_rather_than_failing_the_stage(self, declared, home, bundle, effected):
        """Served from releases.hashicorp.com, which nothing stages into a bundle.
        The alternative is a machine that cannot finish an install because of a
        language server.

        `refused` rather than `Result(True, ...)`. Both keep the stage green, and
        only one of them stops `apply` printing a tick in front
        of a sentence saying nothing was installed.
        """
        _, fetches = effected()

        result = custom.install(declared.find('custom_installers', 'terraform-ls'), LINUX, offline=True)

        assert not result.ok
        assert result.refused
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert custom.HASHICORP in result.detail
        assert fetches.urls == []

    def test_a_behind_binary_is_downloaded_verified_and_placed(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, **{'terraform-ls': '0.38.0'})
        latest(monkeypatch, 'v0.39.0')
        stub_binary(home, 'terraform-ls')
        archive, digest = _zip_with_digest({'terraform-ls': SCRIPT})
        release = 'https://releases.hashicorp.com/terraform-ls/0.39.0'
        asset = 'terraform-ls_0.39.0_linux_amd64.zip'
        effected(
            fetches=Fetches(
                {
                    f'{release}/{asset}': archive,
                    f'{release}/terraform-ls_0.39.0_SHA256SUMS': f'{digest}  {asset}\n'.encode(),
                }
            )
        )

        result = custom.install(declared.find('custom_installers', 'terraform-ls'), LINUX)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'terraform-ls').read_bytes() == SCRIPT

    def test_a_checksum_mismatch_refuses(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, **{'terraform-ls': None})
        latest(monkeypatch, 'v0.39.0')
        archive, _ = _zip_with_digest({'terraform-ls': SCRIPT})
        release = 'https://releases.hashicorp.com/terraform-ls/0.39.0'
        asset = 'terraform-ls_0.39.0_linux_amd64.zip'
        effected(fetches=Fetches({f'{release}/{asset}': archive, f'{release}/terraform-ls_0.39.0_SHA256SUMS': f'0000  {asset}\n'.encode()}))

        result = custom.install(declared.find('custom_installers', 'terraform-ls'), LINUX)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'checksum mismatch' in result.detail

    def test_an_unreadable_checksums_file_refuses_rather_than_warning(self, declared, home, bundle, effected, monkeypatch):
        """HashiCorp publishes one for every release, so failing to get it means
        something is wrong with the download path — which is when it matters."""
        reports(monkeypatch, **{'terraform-ls': None})
        latest(monkeypatch, 'v0.39.0')
        archive, _ = _zip_with_digest({'terraform-ls': SCRIPT})
        release = 'https://releases.hashicorp.com/terraform-ls/0.39.0'
        effected(fetches=Fetches({f'{release}/terraform-ls_0.39.0_linux_amd64.zip': archive}, refuse=('SHA256SUMS',)))

        result = custom.install(declared.find('custom_installers', 'terraform-ls'), LINUX)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'could not be verified' in result.detail


class TestBats:
    def test_a_missing_helper_is_named_rather_than_restored_blind(self, declared, home, bundle, effected):
        """The same reason release companions became measurable: nothing about
        `bats` being current says `~/.local/lib/bats-assert` is still there, and its
        absence surfaces as a failing `load` line in a suite, not here.

        Measured rather than restored blind, which is what lets `check` mention it
        at all — a repair nothing observes is a repair nobody can be told about.
        """
        (home / '.local' / 'lib' / 'bats-support').mkdir(parents=True)

        assert custom.missing_parts(declared.find('custom_installers', 'bats')) == ('bats-assert',)

    def test_both_helpers_present_owes_nothing(self, declared, home, bundle, effected):
        for helper in ('support', 'assert'):
            (home / '.local' / 'lib' / f'bats-{helper}').mkdir(parents=True)

        assert custom.missing_parts(declared.find('custom_installers', 'bats')) == ()

    def test_an_installer_with_no_side_artifacts_owes_nothing(self, declared, home, bundle, effected):
        assert custom.missing_parts(declared.find('custom_installers', 'awscli')) == ()

    def test_an_absent_runner_clones_at_the_tag_and_runs_its_own_installer(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, bats=None)
        latest(monkeypatch, 'v1.14.0')
        stub_binary(home, 'bats')
        runs, _ = effected()

        result = custom.install(declared.find('custom_installers', 'bats'), LINUX)

        assert result.ok, result.detail
        core = next(argv for argv in runs.calls if 'bats-core.git' in ' '.join(argv))
        assert '--branch' in core and 'v1.14.0' in core
        installer = next(argv for argv in runs.calls if argv[0] == 'bash')
        assert installer[-1] == str(home / '.local')

    def test_a_helper_that_will_not_clone_warns_rather_than_failing_the_install(
        self, declared, home, bundle, effected, monkeypatch, capsys
    ):
        """bats runs without them, and a suite that needs one fails loudly at its
        `load` line. Failing here would take the runner away too."""
        reports(monkeypatch, bats=None)
        latest(monkeypatch, 'v1.14.0')
        stub_binary(home, 'bats')
        effected(Runs(**{'bats-assert': Completed(('git',), 128, 'could not read')}))

        result = custom.install(declared.find('custom_installers', 'bats'), LINUX)

        assert result.ok, result.detail
        assert 'bats-assert' in capsys.readouterr().err

    def test_an_upstream_that_will_not_answer_is_a_failure_not_a_guess(self, declared, home, bundle, effected, monkeypatch):
        reports(monkeypatch, bats=None)
        latest(monkeypatch, None)
        effected()

        result = custom.install(declared.find('custom_installers', 'bats'), LINUX)

        assert not result.ok
        assert result.kind is Kind.VERSION_UNRESOLVED


# ─────────────────────────────────────────────────────────────────────────────


def _tarball(members: dict[str, bytes]) -> bytes:
    import io as _io
    import tarfile

    buffer = _io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o755
            archive.addfile(info, _io.BytesIO(payload))
    return buffer.getvalue()


def _zip_with_digest(members: dict[str, bytes]) -> tuple[bytes, str]:
    import hashlib

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    body = buffer.getvalue()
    return body, hashlib.sha256(body).hexdigest()
