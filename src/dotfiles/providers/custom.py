"""The nine tools that ship themselves, one function each.

`github_releases` is twenty-three spellings of one sequence, which is why
`providers/ghrelease.py` is an engine with the variation pushed into a data
class. These nine are the opposite, and that is what `custom_installers` means:
a vendor install script, an S3 bucket with a GPG trust root, a HashiCorp mirror
carrying its own checksums file, and three git repos with a build. No engine fits
them, so this is nine functions and a dispatch table, and the only shared
machinery is the part that genuinely is shared — staging a vendor script from the
offline bundle or the network, and running it.

The install/update split goes the way it went for releases. Each script had two
modes, and which one ran decided whether a tool already present was upgraded;
`apply` means "make this machine match what it declares", so every function here
converges.

**Whether a tool is behind is not asked here.** `resources/packages.CURRENCY`
measures it, off the `repo:` each entry declares, so an installer that is called
is one the machine needs and every function below can simply converge. What
differs between them is only what converging means:

    theme, font, zmk-build   the tool has its own `update`, so delegate to it
    bashselfupdate           the install script is the update, so always run it
    bats, terraform-ls       clone or download at the tag upstream reports
    mount-s3                 the bucket serves `latest/`, so just fetch it
    claude-code              self-updates in the background; presence is enough
    awscli                   no release to compare against; presence is enough

Every failure is returned, never raised: one broken vendor must not stop the
eight after it, and the stage reports all of them together.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import evidence
from dotfiles import github_release
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.output import err_console
from dotfiles.output import warn
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import local_dir
from dotfiles.providers import script


@dc.dataclass(frozen=True, slots=True)
class Request:
    """One tool to converge, and the one flag that changes how.

    There is no force flag and nowhere for one to attach: currency is measured
    before an installer is called, so reaching a function below means the machine
    needs it. A flag overriding that could only mean "write despite the
    measurement", which `cli-design.md` § "A flag never decides whether the command
    writes" rules out.
    """

    entry: catalog.CustomInstaller
    target: Target
    offline: bool = False


Installer = Callable[[Request], Result]


def install(entry: catalog.CustomInstaller, target: Target, *, offline: bool = False) -> Result:
    """Converge one custom installer, whatever converging means for it."""
    installer = INSTALLERS.get(entry.name)
    if installer is None:
        return Result(False, f'nothing in providers.custom installs {entry.name}')
    return installer(Request(entry, target, offline=offline))


def missing_parts(entry: catalog.CustomInstaller) -> tuple[str, ...]:
    """What this tool installs besides its own binary, and is not there. A read.

    The custom-installer twin of `ghrelease.missing_companions`, and it exists for
    the same reason: `bats` is on PATH and current while `~/.local/lib/bats-assert`
    is gone, which surfaces as a failing `load` line in a suite rather than in any
    verdict.

    Empty for eight of the nine — most of these install one binary and nothing
    else — so this is a lookup and not a protocol for each of them to implement.
    """
    if entry.name != 'bats':
        return ()
    return tuple(f'bats-{helper}' for helper in BATS_HELPERS if not (local_dir() / 'lib' / f'bats-{helper}').is_dir())


# ─────────────────────────────────────────────────────────────────────────────
# What each one reaches for
# ─────────────────────────────────────────────────────────────────────────────


class Reach(enum.StrEnum):
    """How a source is contacted, which decides how a probe tests it."""

    DOWNLOAD = 'download'
    CLONE = 'clone'


@dc.dataclass(frozen=True, slots=True)
class Source:
    """One host this installer has to reach before it can do anything."""

    url: str
    reach: Reach = Reach.DOWNLOAD


def sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    """Every URL installing this tool depends on, for a connectivity probe.

    Code rather than a `source_type` the probe switches on, for the reason asset
    naming is code: the shell's switch could express "a github_clone needs
    github.com" but not that `theme` also fetches its install script from
    `raw.githubusercontent.com`, nor that `bats` needs three repos, nor that
    `awscli` names a different zip per architecture. Each of those was either
    unprobed or approximated.

    Empty when this platform installs the tool from somewhere else or not at all,
    which is not a failure — probing then reports a block that does not exist.
    """
    return SOURCES.get(entry.name, _no_sources)(entry, target)


def _no_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return ()


def _script_and_clone(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    """A vendor script that clones the repo it came from — both hosts matter."""
    return (Source(entry.install_url), Source(f'https://github.com/{entry.repo}.git', Reach.CLONE))


def _claude_code_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return (Source(entry.install_url),)


def _bats_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return tuple(Source(url, Reach.CLONE) for url in _bats_repos(entry))


def _awscli_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    url = _awscli_zip(entry, target)
    return (Source(url),) if url else ()


def _mount_s3_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    tarball = _mount_s3_tarball(entry, target)
    # The tarball, never the bucket root: listing it 403s, so probing the root
    # reports a block that is really S3 refusing to enumerate.
    return (Source(tarball), Source(f'{entry.url}/public_keys/KEYS')) if tarball else ()


def _terraform_ls_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    # The project directory, because the file name carries a version that is not
    # known until the release API answers — which the probe must not depend on.
    return (Source(f'{HASHICORP}/{entry.name}/'),)


SOURCES: dict[str, Callable[[catalog.CustomInstaller, Target], tuple[Source, ...]]] = {
    'theme': _script_and_clone,
    'font': _script_and_clone,
    'zmk-build': _script_and_clone,
    'bashselfupdate': _script_and_clone,
    'claude-code': _claude_code_sources,
    'bats': _bats_sources,
    'awscli': _awscli_sources,
    'mount-s3': _mount_s3_sources,
    'terraform-ls': _terraform_ls_sources,
}


# ─────────────────────────────────────────────────────────────────────────────
# Running a vendor's own install script
# ─────────────────────────────────────────────────────────────────────────────


def _staged_script(request: Request, url: str, into: Path) -> Path | None:
    return script.staged(request.entry.name, url, into, offline=request.offline)


def _run_vendor_script(request: Request, url: str) -> Result:
    """Fetch and run one vendor install script.

    Shared with the language runtimes, which converge the same way: `providers/
    script.py` holds it, and an empty detail on success is its rule as much as
    `_delegate_update`'s below.
    """
    return script.run(request.entry.name, url, offline=request.offline)


def _unstaged(request: Request, url: str) -> str:
    return script.unstaged(request.entry.name, url, offline=request.offline)


def _present_and_offline(request: Request, installed: bool) -> Result | None:
    """Offline is a reason to leave a working tool alone, not to fail.

    Every one of these updates from the network — a clone, a vendor script, a
    release API — so an offline run has nothing to compare against and nothing to
    fetch. Reporting the tool present is the honest answer; failing the stage
    would report a machine as broken for being exactly what its bundle made it.
    """
    if request.offline and installed:
        return Result(True, f'{request.entry.name} is installed; offline, so it is not updated')
    return None


# ─────────────────────────────────────────────────────────────────────────────
# The personal CLIs: cloned by a vendor script, updated by themselves
# ─────────────────────────────────────────────────────────────────────────────


def _checkout_tool(request: Request) -> Result:
    """theme, font and zmk-build: install once, then delegate to the tool.

    Each clones itself into `~/.local/share/<name>` and ships its own `update`,
    which knows how to fast-forward that checkout and rebuild whatever it
    generates. Re-running the install script over a live checkout would be a
    second, worse implementation of that.
    """
    name = request.entry.name
    checkout = local_dir() / 'share' / name
    installed = (checkout / '.git').is_dir()

    if offline := _present_and_offline(request, installed):
        return offline
    if installed:
        return _delegate_update(name, checkout)
    return _run_vendor_script(request, request.entry.install_url)


def _delegate_update(name: str, checkout: Path) -> Result:
    if not shutil.which(name):
        return Result(False, f'{name} is checked out at {checkout} but is not on PATH — is {bin_dir()} in it?')
    completed = effects.run([name, 'update'])
    return Result(completed.ok, '' if completed.ok else f'{name} update exited {completed.returncode}')


def _bashselfupdate(request: Request) -> Result:
    """A sourced library, so there is no command to delegate to.

    Its install script *is* its update — it fetches and re-checks-out onto the
    newest tag whether or not the directory is already there — so there is
    deliberately no already-installed exit. The checkout is the only evidence it
    is installed, which is why the entry declares `installed_path`.
    """
    checkout = Path(request.entry.installed_path).expanduser()
    if offline := _present_and_offline(request, checkout.exists()):
        return offline
    return _run_vendor_script(request, request.entry.install_url)


def _claude_code(request: Request) -> Result:
    """Installed by a vendor script, kept current by itself.

    Two things the other script installers do not have. It updates itself in the
    background, so presence is the whole question — re-running the installer would
    fight the thing it is trying to converge. And it refuses to install while
    Claude is running, which on this machine is *always*, because the process
    asking for the install is Claude. That refusal is reported as success: the
    binary already there keeps working, and the next run installs.
    """
    installed = evidence.reported_version(request.entry.executable)
    if installed:
        return Result(True, f'claude-code {installed.splitlines()[0]} (self-updating)')

    with tempfile.TemporaryDirectory(prefix='dotfiles-claude-code-') as scratch:
        script = _staged_script(request, request.entry.install_url, Path(scratch))
        if script is None:
            return Result(False, _unstaged(request, request.entry.install_url))
        completed = effects.run(['bash', str(script)], output=Output.STREAM)

    if completed.ok:
        return Result(True, 'claude-code installed')
    if BUSY_INSTALLING.search(completed.transcript):
        return Result(True, 'claude-code skipped: another process is currently installing it')
    return Result(False, f'the claude-code install script exited {completed.returncode}')


BUSY_INSTALLING = re.compile(r'another process is currently installing|claude.*running', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Vendors with their own distribution
# ─────────────────────────────────────────────────────────────────────────────

AWSCLI_ZIPS = {'x86_64': 'awscli-exe-linux-x86_64.zip', 'arm64': 'awscli-exe-linux-aarch64.zip'}


def _awscli_zip(entry: catalog.CustomInstaller, target: Target) -> str:
    """'' on macOS, where awscli is a Homebrew package and this installs nothing."""
    if target.is_darwin:
        return ''
    return f'{entry.url}/{AWSCLI_ZIPS[target.arch]}'


def _awscli(request: Request) -> Result:
    """AWS's own installer, which is idempotent and expensive — so it is measured first.

    `aws/install --update` converges by itself, so the ideal is to run it every
    time — and it is 73MB every time (measured 2026-08-08), which is why nothing
    runs it without a reason.

    `aws/aws-cli` publishes no GitHub *release* — `releases/latest` answers 404,
    rechecked 2026-08-10 — but it tags every build, and the entry declares
    `version_source: tags` so `_has_currency` can compare against them. Reaching
    here therefore means the machine is missing it or behind, and the 73MB is
    being spent on a difference someone measured.
    """
    if request.target.is_darwin:
        return Result(True, 'awscli is a Homebrew package on macOS, installed with the system packages')

    if offline := _present_and_offline(request, evidence.reported_version(request.entry.executable) is not None):
        return offline
    if request.offline:
        return Result(False, f'awscli installs from {request.entry.url}, which the offline bundle does not stage', refused=True)

    url = _awscli_zip(request.entry, request.target)
    with tempfile.TemporaryDirectory(prefix='dotfiles-awscli-') as scratch:
        staging = Path(scratch)
        archive = staging / 'awscliv2.zip'
        err_console.print(f'awscli: {url}', soft_wrap=True)
        if not effects.fetch(url, archive):
            return Result(False, f'could not download {url}')
        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the awscli zip did not unpack')

        installer = staging / 'unpacked' / 'aws' / 'install'
        if not installer.is_file():
            return Result(False, 'the awscli zip contains no aws/install')
        effects.make_executable(installer)
        completed = effects.run([str(installer), '--install-dir', str(local_dir() / 'aws-cli'), '--bin-dir', str(bin_dir()), '--update'])

    if not completed.ok:
        return Result(False, f"aws's own installer exited {completed.returncode}")
    return _confirm('awscli', request.entry.executable)


MOUNT_S3_ARCHES = {'x86_64': 'x86_64', 'arm64': 'arm64'}

MOUNT_S3_KEYS = (
    '8AEFE705EBE329C0948C75A66F1C3B3AEF4B030B',
    '673FE4061506BB469A0EF857BE397A52B086DA5A',
)
"""AWS's mountpoint-s3 signing keys, from their KEYS file and install docs.

Pinned because the key is served from the same bucket as the tarball it signs:
importing whatever KEYS holds and verifying against it proves only that the
bucket is self-consistent. The first is valid until 2029-03-18, the second
expired 2026-07-31 and stays for signatures made before then.
"""


def _mount_s3_tarball(entry: catalog.CustomInstaller, target: Target) -> str:
    """'' where there is no build: AWS ships mountpoint-s3 for Linux only."""
    if target.is_darwin:
        return ''
    return f'{entry.url}/latest/{MOUNT_S3_ARCHES[target.arch]}/mount-s3.tar.gz'


def _mount_s3(request: Request) -> Result:
    """A tarball from AWS's bucket, verified against a pinned signing key.

    The bucket serves only `latest/`, so the download URL carries no version — but
    `awslabs/mountpoint-s3` publishes the same releases on GitHub, and `mount-s3
    --version` reports the number in that tag. That is what makes skipping
    possible at all: comparing against the release API costs one request, where
    the alternative is fetching the tarball to find out what is in it.
    """
    tarball_url = _mount_s3_tarball(request.entry, request.target)
    if not tarball_url:
        return Result(True, 'mount-s3 has no macOS build, so nothing is installed here')

    installed = evidence.reported_version(request.entry.executable)
    if offline := _present_and_offline(request, installed is not None):
        return offline

    with tempfile.TemporaryDirectory(prefix='dotfiles-mount-s3-') as scratch:
        staging = Path(scratch)
        archive = staging / 'mount-s3.tar.gz'
        err_console.print(f'mount-s3: {tarball_url}', soft_wrap=True)
        if not effects.fetch(tarball_url, archive):
            return Result(False, f'could not download {tarball_url}')

        refused = _verify_signature(archive, tarball_url, f'{request.entry.url}/public_keys/KEYS', staging)
        if refused:
            return Result(False, refused)

        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the mount-s3 tarball did not unpack')
        binary = staging / 'unpacked' / 'bin' / 'mount-s3'
        if not binary.is_file():
            return Result(False, 'the mount-s3 tarball contains no bin/mount-s3')
        _place(binary, request.entry.executable)

    if not _have_fuse():
        warn('libfuse2 is not installed, so mount-s3 can run but cannot mount (apt: libfuse2, pacman: fuse2)')
    return _confirm('mount-s3', request.entry.executable)


def _verify_signature(archive: Path, tarball_url: str, keys_url: str, staging: Path) -> str:
    """'' when the tarball's detached signature checks out, else why it does not.

    Fails closed on a bad signature or an unpinned key, and warns without refusing
    when the signature or gpg itself is unavailable — the same split the shell made,
    for the same reason: a machine with no gnupg has not been shown a bad signature,
    it has been unable to look.
    """
    if not shutil.which('gpg'):
        warn('gpg is not installed, so the mount-s3 signature could not be checked')
        return ''

    signature = staging / 'mount-s3.tar.gz.asc'
    keys = staging / 'KEYS'
    if not effects.fetch(f'{tarball_url}.asc', signature) or not effects.fetch(keys_url, keys):
        warn('could not fetch the mount-s3 signature or signing keys, so the signature was not checked')
        return ''

    home = staging / 'gnupg'
    home.mkdir(mode=0o700)
    environment = {'GNUPGHOME': str(home)}
    effects.run(['gpg', '--quiet', '--import', str(keys)], env=environment, output=Output.QUIET)

    listed = effects.run(['gpg', '--list-keys', '--with-colons'], env=environment, output=Output.QUIET)
    fingerprints = {line.split(':')[9] for line in listed.transcript.splitlines() if line.startswith('fpr:')}
    if not fingerprints & set(MOUNT_S3_KEYS):
        return 'the mount-s3 signing key is not one of the pinned fingerprints'

    verified = effects.run(['gpg', '--verify', str(signature), str(archive)], env=environment, output=Output.QUIET)
    return '' if verified.ok else 'the mount-s3 GPG signature did not verify'


def _have_fuse() -> bool:
    listed = effects.run(['ldconfig', '-p'], output=Output.QUIET)
    return listed.ok and 'libfuse.so.2' in listed.transcript


HASHICORP = 'https://releases.hashicorp.com'

TERRAFORM_LS_ARCHES = {'x86_64': 'amd64', 'arm64': 'arm64'}


def _terraform_ls(request: Request) -> Result:
    """Released on GitHub, distributed from HashiCorp's own mirror.

    Which is the whole reason it is not a `github_releases` entry: the version
    comes from the release API, and the zip and its `SHA256SUMS` come from
    `releases.hashicorp.com`, so the checksum file cannot be discovered among the
    release assets and has to be named directly.

    Nothing stages it into an offline bundle for the same reason, so an offline
    run refuses it rather than failing the stage — the alternative is a machine
    that cannot finish an install because of a language server.
    """
    entry = request.entry
    if request.offline:
        return Result(False, f'terraform-ls is served from {HASHICORP}, which the offline bundle does not stage', refused=True)

    latest = github_release.latest_version(entry.repo, '')
    if latest is None:
        return Result(False, f'{entry.repo} did not answer with a release')

    version = latest.lstrip('v')
    os_word = 'darwin' if request.target.is_darwin else 'linux'
    release = f'{HASHICORP}/terraform-ls/{version}'
    asset = f'terraform-ls_{version}_{os_word}_{TERRAFORM_LS_ARCHES[request.target.arch]}.zip'

    with tempfile.TemporaryDirectory(prefix='dotfiles-terraform-ls-') as scratch:
        staging = Path(scratch)
        archive = staging / asset
        err_console.print(f'terraform-ls {latest}: {release}/{asset}', soft_wrap=True)
        if not effects.fetch(f'{release}/{asset}', archive):
            return Result(False, f'could not download {release}/{asset}')

        refused = _verify_checksum(archive, asset, f'{release}/terraform-ls_{version}_SHA256SUMS', staging)
        if refused:
            return Result(False, refused)

        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the terraform-ls zip did not unpack')
        binary = staging / 'unpacked' / 'terraform-ls'
        if not binary.is_file():
            return Result(False, 'the terraform-ls zip contains no terraform-ls')
        _place(binary, entry.executable)

    return _confirm(f'terraform-ls {latest}', entry.executable)


def _verify_checksum(archive: Path, asset_name: str, checksums_url: str, staging: Path) -> str:
    """'' when the download matches the published digest, else why it does not.

    Refuses rather than warns when the checksums file cannot be read: HashiCorp
    publishes one for every release, so failing to get it means something is wrong
    with the download path, and that is exactly when a checksum matters.
    """
    published = staging / 'SHA256SUMS'
    if not effects.fetch(checksums_url, published):
        return f'could not download {checksums_url}, so {asset_name} could not be verified'

    expected = github_release.checksum_for_asset(published.read_text(errors='replace'), asset_name)
    if expected is None:
        return f'{checksums_url} does not name {asset_name}'
    if not github_release.digests_match(expected, github_release.sha256_of(archive)):
        return f'checksum mismatch for {asset_name}'
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Built from source
# ─────────────────────────────────────────────────────────────────────────────

BATS_HELPERS = ('support', 'assert')


def _bats_repos(entry: catalog.CustomInstaller) -> tuple[str, ...]:
    return tuple(f'https://github.com/{slug}.git' for slug in (entry.repo, entry.support_repo, entry.assert_repo))


def _bats(request: Request) -> Result:
    """Three repos: the test runner, and the two assertion libraries it loads.

    The runner is cloned at a tag and installs itself with its own `install.sh`.
    The helpers are cloned at HEAD and copied into `~/.local/lib`, where the
    `load` lines in the bats suites expect them — they are unversioned upstream,
    with no tags to pin to.

    A helper that will not clone is a warning rather than a failure: bats itself
    runs without them, and a suite that needs one fails loudly at its `load` line
    with a message naming the file. Failing the whole install instead would take
    the runner away too.
    """
    entry = request.entry
    installed = evidence.reported_version(entry.executable)
    if offline := _present_and_offline(request, installed is not None):
        return offline

    latest = github_release.latest_version(entry.repo, '')
    if latest is None:
        return Result(False, f'{entry.repo} did not answer with a release')

    core = _bats_repos(entry)[0]
    with tempfile.TemporaryDirectory(prefix='dotfiles-bats-') as scratch:
        checkout = Path(scratch) / 'bats-core'
        err_console.print(f'bats {latest}: {core}', soft_wrap=True)
        cloned = effects.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', latest, core, str(checkout)])
        if not cloned.ok:
            return Result(False, f'could not clone {core} at {latest}')

        completed = effects.run(['bash', str(checkout / 'install.sh'), str(local_dir())])
        if not completed.ok:
            return Result(False, f"bats-core's own install.sh exited {completed.returncode}")

    _install_bats_helpers(entry)
    return _confirm(f'bats {latest}', entry.executable)


def _install_bats_helpers(entry: catalog.CustomInstaller) -> None:
    """The two assertion libraries, refreshed alongside the runner.

    Always both, never only the absent ones: reaching here means the runner is
    being installed, and the three pieces are meant to be one set. Whether a helper
    is *missing* is `missing_parts`, and it is a question for the observation rather
    than for this.
    """
    _, support, assertions = _bats_repos(entry)
    for url, helper in zip((support, assertions), BATS_HELPERS, strict=True):
        _clone_bats_helper(url, helper)


def _clone_bats_helper(url: str, helper: str) -> None:
    destination = local_dir() / 'lib' / f'bats-{helper}'

    with tempfile.TemporaryDirectory(prefix=f'dotfiles-bats-{helper}-') as scratch:
        checkout = Path(scratch) / helper
        cloned = effects.run(['git', 'clone', '--quiet', '--depth', '1', url, str(checkout)], output=Output.QUIET)
        if not cloned.ok or not checkout.is_dir():
            warn(f'could not clone bats-{helper} from {url}; bats runs without it, but a suite loading it will fail')
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(checkout), destination)


# ─────────────────────────────────────────────────────────────────────────────


def _place(binary: Path, executable: str) -> None:
    """Move one unpacked binary into `~/.local/bin` under the name it is called by."""
    destination = bin_dir() / executable
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(binary), destination)
    effects.make_executable(destination)


def _confirm(what: str, executable: str) -> Result:
    """Everything above ends here: installed is a claim PATH has to agree with."""
    if not shutil.which(executable):
        return Result(False, f'{executable} installed but is not on PATH — is {bin_dir()} in it?')
    return Result(True, what)


INSTALLERS: dict[str, Installer] = {
    'theme': _checkout_tool,
    'font': _checkout_tool,
    'zmk-build': _checkout_tool,
    'bashselfupdate': _bashselfupdate,
    'claude-code': _claude_code,
    'awscli': _awscli,
    'mount-s3': _mount_s3,
    'terraform-ls': _terraform_ls,
    'bats': _bats,
}
"""Which function installs which entry.

`validate.py` checks this against `packages.yml` in one direction and
`tests/install/test_custom_installers.py` in the other, so an entry nothing can
install and a function nothing declares are both errors rather than silence.
"""
