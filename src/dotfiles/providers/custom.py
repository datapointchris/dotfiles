"""The tools that ship themselves, one function each.

`github_releases` is many spellings of one sequence, which is why
`providers/ghrelease.py` is an engine with the variation pushed into a data
class. These are the opposite, and that is what `custom_installers` means:
a vendor install script, an S3 bucket with a GPG trust root, a HashiCorp mirror
carrying its own checksums file, git repos with a build, and git's own source
compiled. No engine fits them, so this is a function each and a dispatch table,
and the only shared machinery is the part that genuinely is shared — staging a
vendor script from the offline bundle or the network, and running it.

The install/update split goes the way it went for releases. Each script had two
modes, and which one ran decided whether a tool already present was upgraded;
`apply` means "make this machine match what it declares", so every function here
converges.

**Whether a tool is behind is not asked here.** `resources/packages.CURRENCY`
measures it, off the `repo:` each entry declares or the vendor file
`version_file` names, so an installer that is called is one the machine needs
and every function below can simply converge. What differs between them is only
what converging means:

    theme, font, zmk         the tool has its own `update`, so delegate to it
    bashselfupdate           the install script is the update, so always run it
    claude-code              the install script is the update, so run it
    bats, terraform-ls       clone or download at the tag upstream reports
    git                      clone the tag upstream reports, and build it
    mount-s3                 the bucket serves `latest/`, so just fetch it
    awscli                   AWS's installer takes `--update`, so run it

Every failure is returned, never raised: one broken vendor must not stop the
ones after it, and the stage reports all of them together.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import evidence
from dotfiles import github_release
from dotfiles import paths
from dotfiles import routing
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.output import err_console
from dotfiles.output import warn
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import local_dir
from dotfiles.providers import script
from dotfiles.providers import unreadable_kind


@dc.dataclass(frozen=True, slots=True)
class Request:
    """One tool to converge, and which hosts this run may reach for it.

    There is no force flag and nowhere for one to attach: currency is measured
    before an installer is called, so reaching a function below means the machine
    needs it. A flag overriding that could only mean "write despite the
    measurement", and a flag never decides whether the command writes.

    The routes rather than one offline flag, because one installer reaches several
    hosts. `theme` takes its script from a host the work network blocks and clones
    from one it allows, so each URL is asked about separately.
    """

    entry: catalog.CustomInstaller
    target: Target
    routes: routing.Routes = dc.field(default_factory=routing.Routes)

    def blocked(self, url: str) -> str:
        """'' where this run reaches the URL's host, else the clause saying why not."""
        route = self.routes.route(routing.ItemHosts(download=routing.hosts_of([url])))
        return route.because if route.bundled else ''


Installer = Callable[[Request], Result]


def install(entry: catalog.CustomInstaller, target: Target, *, routes: routing.Routes | None = None) -> Result:
    """Converge one custom installer, whatever converging means for it."""
    installer = INSTALLERS.get(entry.name)
    if installer is None:
        return Result(False, f'nothing in providers.custom installs {entry.name}', kind=Kind.DECLARATION_INVALID)
    return installer(Request(entry, target, routes or routing.Routes()))


def hosts(entry: catalog.CustomInstaller, target: Target) -> routing.ItemHosts:
    """The hosts this tool's version check asks, and the hosts its install reaches.

    The download half is `sources`, the same list `dotfiles network check` probes.
    A checkout tool's update is its own `update` over git, so its update half is
    the clone alone.
    """
    version = {routing.GITHUB_API} if entry.repo else set()
    return routing.ItemHosts(
        version=frozenset(version) | routing.hosts_of(filter(None, [version_file(entry)])),
        download=routing.hosts_of(source.url for source in sources(entry, target)),
        update=routing.hosts_of([git_repo(entry)]) if INSTALLERS.get(entry.name) is checkout_tool else None,
    )


def missing_parts(entry: catalog.CustomInstaller) -> tuple[str, ...]:
    """What this tool installs besides its own binary, and is not there. A read.

    The custom-installer twin of `ghrelease.missing_companions`, and it exists for
    the same reason: `bats` is on PATH and current while `~/.local/lib/bats-assert`
    is gone, which surfaces as a failing `load` line in a suite rather than in any
    verdict.

    Empty for all but bats — the rest install one binary and nothing else, or
    a tree its own build lays out — so this is a lookup and not a protocol for
    each of them to implement.
    """
    if entry.name != 'bats':
        return ()
    return tuple(f'bats-{helper}' for helper in BATS_HELPERS if not (local_dir() / 'lib' / f'bats-{helper}').is_dir())


CLAUDE_CODE_CHANNEL = 'latest'
"""The channel file Claude Code's install script reads, under the entry's `url`.

The script downloads the release this file names and runs its `claude install`
with no target. That installs the channel Claude's own settings choose, which
defaults to this one. A machine whose settings choose `stable` installs an older
release than this file names, so it reads behind after every apply.
"""


def version_file(entry: catalog.CustomInstaller) -> str:
    """Where a vendor publishes its newest version itself, or ''.

    The custom-installer twin of an entry's `repo:`, and code for the reason
    asset naming is: the host is declared, and which file on it names the
    version is the vendor's layout. Empty for every entry but claude-code, which
    leaves the rest measured against their `repo` or not at all.
    """
    if entry.name != 'claude-code' or not entry.url:
        return ''
    return f'{entry.url}/{CLAUDE_CODE_CHANNEL}'


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
    return SOURCES.get(entry.name, no_sources)(entry, target)


def no_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return ()


def script_and_clone(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    """A vendor script that clones the repo it came from — both hosts matter."""
    return (Source(entry.install_url), Source(f'https://github.com/{entry.repo}.git', Reach.CLONE))


def claude_code_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    """The script, and the channel file on the host the script downloads the release from."""
    return (Source(entry.install_url), Source(version_file(entry))) if entry.url else (Source(entry.install_url),)


def bats_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return tuple(Source(url, Reach.CLONE) for url in bats_repos(entry))


def git_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    return (Source(git_repo(entry), Reach.CLONE),)


def awscli_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    url = awscli_zip(entry, target)
    return (Source(url),) if url else ()


def mount_s3_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    tarball = mount_s3_tarball(entry, target)
    # The tarball, never the bucket root: listing it 403s, so probing the root
    # reports a block that is really S3 refusing to enumerate.
    return (Source(tarball), Source(f'{entry.url}/public_keys/KEYS')) if tarball else ()


def terraform_ls_sources(entry: catalog.CustomInstaller, target: Target) -> tuple[Source, ...]:
    # The project directory, because the file name carries a version that is not
    # known until the release API answers — which the probe must not depend on.
    return (Source(f'{HASHICORP}/{entry.name}/'),)


SOURCES: dict[str, Callable[[catalog.CustomInstaller, Target], tuple[Source, ...]]] = {
    'theme': script_and_clone,
    'font': script_and_clone,
    'zmk': script_and_clone,
    'bashselfupdate': script_and_clone,
    'claude-code': claude_code_sources,
    'bats': bats_sources,
    'git': git_sources,
    'awscli': awscli_sources,
    'mount-s3': mount_s3_sources,
    'terraform-ls': terraform_ls_sources,
}


# ─────────────────────────────────────────────────────────────────────────────
# Running a vendor's own install script
# ─────────────────────────────────────────────────────────────────────────────


def staged_script(request: Request, url: str, into: Path) -> script.Script:
    return script.staged(request.entry.name, url, into, offline=bool(request.blocked(url)))


def run_vendor_script(request: Request, url: str) -> Result:
    """Fetch and run one vendor install script, from the bundle where its host is blocked.

    Shared with the language runtimes, which converge the same way: `providers/
    script.py` holds it, and an empty detail on success is its rule as much as
    `delegate_update`'s below.
    """
    why = request.blocked(url)
    return script.run(request.entry.name, url, offline=bool(why), because=why)


def unstaged(request: Request, url: str, reason: str = '') -> str:
    if why := request.blocked(url):
        return f'{request.entry.name} installs from {url}; {why}, and no bundle staged at {paths.staging_dir()} carries its script'
    return script.unstaged(request.entry.name, url, offline=False, reason=reason)


def left_alone(request: Request, installed: bool, *urls: str) -> Result | None:
    """A working tool whose update reaches a blocked host is left as it is, not failed.

    Failing the stage would report a machine as broken for being exactly what its
    network allows. The row names the host, so the reason is on the screen.
    """
    why = next((reason for url in urls if (reason := request.blocked(url))), '')
    if installed and why:
        return Result(True, f'{request.entry.name} is installed and not updated: {why}', kind=Kind.UNCHANGED)
    return None


def cannot_reach(request: Request, what: str, *urls: str) -> Result | None:
    """A refusal where installing this tool reaches a blocked host and no bundle carries it."""
    blocked = next(((url, reason) for url in urls if (reason := request.blocked(url))), None)
    if blocked is None:
        return None
    url, why = blocked
    return Result(False, f'{what} installs from {url}; {why}, and no bundle stages it', kind=Kind.NOT_IN_BUNDLE, refused=True)


# ─────────────────────────────────────────────────────────────────────────────
# The personal CLIs: cloned by a vendor script, updated by themselves
# ─────────────────────────────────────────────────────────────────────────────


def checkout_tool(request: Request) -> Result:
    """theme, font and zmk: install once, then delegate to the tool.

    Each clones itself into `~/.local/share/<name>` and ships its own `update`,
    which knows how to fast-forward that checkout and rebuild whatever it
    generates. Re-running the install script over a live checkout would be a
    second, worse implementation of that.
    """
    name = request.entry.name
    checkout = local_dir() / 'share' / name
    installed = (checkout / '.git').is_dir()

    if kept := left_alone(request, installed, git_repo(request.entry)):
        return kept
    if installed:
        return delegate_update(name, checkout)
    return run_vendor_script(request, request.entry.install_url)


def delegate_update(name: str, checkout: Path) -> Result:
    if not shutil.which(name):
        return Result(False, f'{name} is checked out at {checkout} but is not on PATH — is {bin_dir()} in it?', kind=Kind.NOT_ON_PATH)
    completed = effects.run([name, 'update'])
    return Result(
        completed.ok,
        '' if completed.ok else f'{name} update exited {completed.returncode}',
        kind=Kind.APPLIED if completed.ok else Kind.COMMAND_FAILED,
    )


def bashselfupdate(request: Request) -> Result:
    """A sourced library, so there is no command to delegate to.

    Its install script *is* its update — it fetches and re-checks-out onto the
    newest tag whether or not the directory is already there — so there is
    deliberately no already-installed exit. The checkout is the only evidence it
    is installed, which is why the entry declares `installed_path`.
    """
    checkout = Path(request.entry.installed_path).expanduser()
    if kept := left_alone(request, checkout.exists(), git_repo(request.entry)):
        return kept
    return run_vendor_script(request, request.entry.install_url)


def claude_code(request: Request) -> Result:
    """Anthropic's install script, which is the upgrade as well as the install.

    Claude Code updates itself in the background on a desk, and a machine that
    only ever runs `claude -p` falls behind. So presence is not currency, and
    reaching here means missing or behind. Both converge the same way.

    The script rather than `claude update`. Both end in the same install routine
    under the same lock, but `claude update` runs it from the installed binary,
    which is the stale one. The script downloads the release its channel file
    names and runs *that* binary's installer, and it is the path the offline
    bundle already stages.

    The lock is also taken by the background updater on an interactive machine.
    Losing it is reported as unchanged: the process holding it is installing, and
    the next run measures whether the release arrived.
    """
    installed = evidence.reported_version(request.entry.executable) is not None
    if kept := left_alone(request, installed, request.entry.url):
        return kept

    blocked = bool(request.blocked(request.entry.install_url))
    with tempfile.TemporaryDirectory(prefix='dotfiles-claude-code-') as scratch:
        # Named before it is reached, as `theme`, `font` and the runtimes do through
        # `script.run`. This installer stages by hand and printed nothing, so it was
        # the one vendor script whose URL never reached the screen — on a firewalled
        # machine that is the single most useful line, because the host is what a
        # person has to get unblocked.
        source = f'from the bundle, because {request.blocked(request.entry.install_url)}' if blocked else request.entry.install_url
        err_console.print(f'claude-code: {source}', soft_wrap=True)
        staged = staged_script(request, request.entry.install_url, Path(scratch))
        if not staged:
            # `refused` where the bundle simply does not carry it, matching every
            # other installer: a machine that cannot reach the script's host and was
            # never given it is doing what it was built to do, and reporting a
            # failure makes the whole stage non-zero for it.
            return Result(
                False,
                unstaged(request, request.entry.install_url, staged.reason),
                kind=Kind.NOT_IN_BUNDLE if blocked else Kind.DOWNLOAD_FAILED,
                refused=blocked,
            )
        completed = effects.run(['bash', str(staged.path)], output=Output.STREAM)

    if completed.ok:
        return Result(True, 'claude-code installed', kind=Kind.APPLIED)
    if BUSY_INSTALLING.search(completed.transcript):
        return Result(True, 'claude-code skipped: another process is currently installing it', kind=Kind.UNCHANGED)
    return Result(False, script.failure('claude-code', completed), kind=Kind.COMMAND_FAILED)


BUSY_INSTALLING = re.compile(r'another process is currently installing|claude.*running', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Vendors with their own distribution
# ─────────────────────────────────────────────────────────────────────────────

AWSCLI_ZIPS = {'x86_64': 'awscli-exe-linux-x86_64.zip', 'arm64': 'awscli-exe-linux-aarch64.zip'}


def awscli_zip(entry: catalog.CustomInstaller, target: Target) -> str:
    """'' on macOS, where awscli is a Homebrew package and this installs nothing."""
    if target.is_darwin:
        return ''
    return f'{entry.url}/{AWSCLI_ZIPS[target.arch]}'


def awscli(request: Request) -> Result:
    """AWS's own installer, which is idempotent and expensive — so it is measured first.

    `aws/install --update` converges by itself, so the ideal is to run it every
    time — and it is a 73MB download every time, which is why nothing runs it
    without a reason.

    `aws/aws-cli` publishes no GitHub *release* — `releases/latest` answers 404 —
    but it tags every build, and the entry declares
    `version_source: tags` so `has_currency` can compare against them. Reaching
    here therefore means the machine is missing it or behind, and the 73MB is
    being spent on a difference someone measured.

    macOS never reaches this at all: Homebrew has the formula, and the entry
    declares `excludes_os_family: darwin` so the item is not planned there. That
    was a branch here returning success without installing anything, which left
    a Mac with nothing wrong printing a line about awscli on every run.
    """
    url = awscli_zip(request.entry, request.target)
    if kept := left_alone(request, evidence.reported_version(request.entry.executable) is not None, url):
        return kept
    if stopped := cannot_reach(request, 'awscli', url):
        return stopped

    with tempfile.TemporaryDirectory(prefix='dotfiles-awscli-') as scratch:
        staging = Path(scratch)
        archive = staging / 'awscliv2.zip'
        err_console.print(f'awscli: {url}', soft_wrap=True)
        arrived = effects.fetch(url, archive)
        if not arrived:
            return Result(False, f'could not download {url}: {arrived.reason}', kind=Kind.DOWNLOAD_FAILED)
        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the awscli zip did not unpack', kind=Kind.ARCHIVE_UNREADABLE)

        installer = staging / 'unpacked' / 'aws' / 'install'
        if not installer.is_file():
            return Result(False, 'the awscli zip contains no aws/install', kind=Kind.ARCHIVE_INCOMPLETE)
        effects.make_executable(installer)
        completed = effects.run([str(installer), '--install-dir', str(local_dir() / 'aws-cli'), '--bin-dir', str(bin_dir()), '--update'])

    if not completed.ok:
        return Result(False, f"aws's own installer exited {completed.returncode}", kind=Kind.COMMAND_FAILED)
    return confirm_on_path('awscli', request.entry.executable)


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


def mount_s3_tarball(entry: catalog.CustomInstaller, target: Target) -> str:
    """'' where there is no build: AWS ships mountpoint-s3 for Linux only."""
    if target.is_darwin:
        return ''
    return f'{entry.url}/latest/{MOUNT_S3_ARCHES[target.arch]}/mount-s3.tar.gz'


def mount_s3(request: Request) -> Result:
    """A tarball from AWS's bucket, verified against a pinned signing key.

    The bucket serves only `latest/`, so the download URL carries no version — but
    `awslabs/mountpoint-s3` publishes the same releases on GitHub, and `mount-s3
    --version` reports the number in that tag. That is what makes skipping
    possible at all: comparing against the release API costs one request, where
    the alternative is fetching the tarball to find out what is in it.
    """
    tarball_url = mount_s3_tarball(request.entry, request.target)
    if not tarball_url:
        return Result(True, 'mount-s3 has no macOS build, so nothing is installed here', kind=Kind.UNSUPPORTED_HERE)

    installed = evidence.reported_version(request.entry.executable)
    if kept := left_alone(request, installed is not None, tarball_url):
        return kept
    if stopped := cannot_reach(request, 'mount-s3', tarball_url):
        return stopped

    with tempfile.TemporaryDirectory(prefix='dotfiles-mount-s3-') as scratch:
        staging = Path(scratch)
        archive = staging / 'mount-s3.tar.gz'
        err_console.print(f'mount-s3: {tarball_url}', soft_wrap=True)
        arrived = effects.fetch(tarball_url, archive)
        if not arrived:
            return Result(False, f'could not download {tarball_url}: {arrived.reason}', kind=Kind.DOWNLOAD_FAILED)

        refused = verify_signature(archive, tarball_url, f'{request.entry.url}/public_keys/KEYS', staging)
        if refused:
            return Result(False, refused, kind=Kind.UNVERIFIED)

        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the mount-s3 tarball did not unpack', kind=Kind.ARCHIVE_UNREADABLE)
        binary = staging / 'unpacked' / 'bin' / 'mount-s3'
        if not binary.is_file():
            return Result(False, 'the mount-s3 tarball contains no bin/mount-s3', kind=Kind.ARCHIVE_INCOMPLETE)
        place(binary, request.entry.executable)

    if not have_fuse():
        warn('libfuse2 is not installed, so mount-s3 can run but cannot mount (apt: libfuse2, pacman: fuse2)')
    return confirm_on_path('mount-s3', request.entry.executable)


def verify_signature(archive: Path, tarball_url: str, keys_url: str, staging: Path) -> str:
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
    fingerprints = {line.split(':')[9] for line in listed.stdout.splitlines() if line.startswith('fpr:')}
    if not fingerprints & set(MOUNT_S3_KEYS):
        return 'the mount-s3 signing key is not one of the pinned fingerprints'

    verified = effects.run(['gpg', '--verify', str(signature), str(archive)], env=environment, output=Output.QUIET)
    return '' if verified.ok else 'the mount-s3 GPG signature did not verify'


def have_fuse() -> bool:
    listed = effects.run(['ldconfig', '-p'], output=Output.QUIET)
    return listed.ok and 'libfuse.so.2' in listed.transcript


HASHICORP = 'https://releases.hashicorp.com'

TERRAFORM_LS_ARCHES = {'x86_64': 'amd64', 'arm64': 'arm64'}


def terraform_ls(request: Request) -> Result:
    """Released on GitHub, distributed from HashiCorp's own mirror.

    Which is the whole reason it is not a `github_releases` entry: the version
    comes from the release API, and the zip and its `SHA256SUMS` come from
    `releases.hashicorp.com`, so the checksum file cannot be discovered among the
    release assets and has to be named directly.

    Nothing stages it into a bundle for the same reason, so a run that cannot reach
    either host refuses it rather than failing the stage — the alternative is a
    machine that cannot finish an install because of a language server.
    """
    entry = request.entry
    api = f'https://{routing.GITHUB_API}'
    if kept := left_alone(request, evidence.reported_version(entry.executable) is not None, HASHICORP, api):
        return kept
    if stopped := cannot_reach(request, 'terraform-ls', HASHICORP, api):
        return stopped

    try:
        latest = github_release.latest_version(entry.repo, '')
    except github_release.Unreadable as unreachable:
        return Result(False, str(unreachable), kind=unreadable_kind(unreachable.reached))
    if latest is None:
        return Result(False, f'{entry.repo} publishes no release', kind=Kind.VERSION_UNRESOLVED)

    version = latest.lstrip('v')
    os_word = 'darwin' if request.target.is_darwin else 'linux'
    release = f'{HASHICORP}/terraform-ls/{version}'
    asset = f'terraform-ls_{version}_{os_word}_{TERRAFORM_LS_ARCHES[request.target.arch]}.zip'

    with tempfile.TemporaryDirectory(prefix='dotfiles-terraform-ls-') as scratch:
        staging = Path(scratch)
        archive = staging / asset
        err_console.print(f'terraform-ls {latest}: {release}/{asset}', soft_wrap=True)
        arrived = effects.fetch(f'{release}/{asset}', archive)
        if not arrived:
            return Result(False, f'could not download {release}/{asset}: {arrived.reason}', kind=Kind.DOWNLOAD_FAILED)

        refused = verify_checksum(archive, asset, f'{release}/terraform-ls_{version}_SHA256SUMS', staging)
        if refused:
            return Result(False, refused, kind=Kind.UNVERIFIED)

        if not effects.unpack(archive, staging / 'unpacked'):
            return Result(False, 'the terraform-ls zip did not unpack', kind=Kind.ARCHIVE_UNREADABLE)
        binary = staging / 'unpacked' / 'terraform-ls'
        if not binary.is_file():
            return Result(False, 'the terraform-ls zip contains no terraform-ls', kind=Kind.ARCHIVE_INCOMPLETE)
        place(binary, entry.executable)

    return confirm_on_path(f'terraform-ls {latest}', entry.executable)


def verify_checksum(archive: Path, asset_name: str, checksums_url: str, staging: Path) -> str:
    """'' when the download matches the published digest, else why it does not.

    Refuses rather than warns when the checksums file cannot be read: HashiCorp
    publishes one for every release, so failing to get it means something is wrong
    with the download path, and that is exactly when a checksum matters.
    """
    published = staging / 'SHA256SUMS'
    arrived = effects.fetch(checksums_url, published)
    if not arrived:
        # The reason matters most here of anywhere: the whole justification for
        # refusing rather than warning is that a miss indicates something specific
        # about the download path, and the message named nothing specific.
        return f'could not download {checksums_url}, so {asset_name} could not be verified: {arrived.reason}'

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


def bats_repos(entry: catalog.CustomInstaller) -> tuple[str, ...]:
    return tuple(f'https://github.com/{slug}.git' for slug in (entry.repo, entry.support_repo, entry.assert_repo))


def bats(request: Request) -> Result:
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
    api = f'https://{routing.GITHUB_API}'
    core_repo = bats_repos(entry)[0]
    if kept := left_alone(request, installed is not None, api, core_repo):
        return kept
    if stopped := cannot_reach(request, 'bats', api, core_repo):
        return stopped

    try:
        latest = github_release.latest_version(entry.repo, '')
    except github_release.Unreadable as unreachable:
        return Result(False, str(unreachable), kind=unreadable_kind(unreachable.reached))
    if latest is None:
        return Result(False, f'{entry.repo} publishes no release', kind=Kind.VERSION_UNRESOLVED)

    core = bats_repos(entry)[0]
    with tempfile.TemporaryDirectory(prefix='dotfiles-bats-') as scratch:
        checkout = Path(scratch) / 'bats-core'
        err_console.print(f'bats {latest}: {core}', soft_wrap=True)
        cloned = effects.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', latest, core, str(checkout)])
        if not cloned.ok:
            return Result(False, f'could not clone {core} at {latest}', kind=Kind.DOWNLOAD_FAILED)

        completed = effects.run(['bash', str(checkout / 'install.sh'), str(local_dir())])
        if not completed.ok:
            return Result(False, f"bats-core's own install.sh exited {completed.returncode}", kind=Kind.COMMAND_FAILED)

    install_bats_helpers(entry)
    return confirm_on_path(f'bats {latest}', entry.executable)


def install_bats_helpers(entry: catalog.CustomInstaller) -> None:
    """The two assertion libraries, refreshed alongside the runner.

    Always both, never only the absent ones: reaching here means the runner is
    being installed, and the three pieces are meant to be one set. Whether a helper
    is *missing* is `missing_parts`, and it is a question for the observation rather
    than for this.
    """
    _, support, assertions = bats_repos(entry)
    for url, helper in zip((support, assertions), BATS_HELPERS, strict=True):
        clone_bats_helper(url, helper)


def clone_bats_helper(url: str, helper: str) -> None:
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


GIT_LEFT_OUT = ('NO_GETTEXT=YesPlease', 'NO_EXPAT=YesPlease', 'NO_RUST=YesPlease', 'NO_TCLTK=YesPlease')
"""What the build leaves out, each for want of something a server lacks.

gettext translates messages, and compiling them needs `msgfmt`. expat serves
only `git http-push`, pushing over WebDAV, which GitHub does not speak. Rust
builds parts that also exist in C, and needs cargo; git 3.0 makes it mandatory.
Tcl/Tk is gitk and git gui, which need a display.
"""


def git_repo(entry: catalog.CustomInstaller) -> str:
    return f'https://github.com/{entry.repo}.git'


def git(request: Request) -> Result:
    """git's newest release tag, compiled into `~/.local`.

    For a machine whose OS packages a git too old for what it runs. git
    publishes tags and source and no binaries, so a build is the one route that
    follows upstream. The OS's git stays: it cloned this repo before anything
    here ran, and it is what clones the source below.

    `~/.local/bin/git` has to come before `/usr/bin/git` on PATH, so the last
    check is which one PATH finds, not whether it finds one.
    """
    entry = request.entry
    api = f'https://{routing.GITHUB_API}'
    if kept := left_alone(request, evidence.reported_version(entry.executable) is not None, api, git_repo(entry)):
        return kept
    if stopped := cannot_reach(request, 'git', api, git_repo(entry)):
        return stopped

    latest = github_release.latest_tag(entry.repo)
    if latest is None:
        return Result(False, f'could not read a release tag from {entry.repo}', kind=Kind.VERSION_UNRESOLVED)

    with tempfile.TemporaryDirectory(prefix='dotfiles-git-') as scratch:
        checkout = Path(scratch) / 'git'
        err_console.print(f'git {latest}: {git_repo(entry)}', soft_wrap=True)
        cloned = effects.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', latest, git_repo(entry), str(checkout)])
        if not cloned.ok:
            return Result(False, f'could not clone {git_repo(entry)} at {latest}', kind=Kind.DOWNLOAD_FAILED)

        built = effects.run(['make', f'-j{os.cpu_count() or 1}', f'prefix={local_dir()}', *GIT_LEFT_OUT, 'install'], cwd=checkout)
        if not built.ok:
            return Result(False, script.failure('git', built), kind=Kind.COMMAND_FAILED)

    found = shutil.which(entry.executable)
    if found is None or Path(found) != bin_dir() / entry.executable:
        return Result(False, f'git {latest} is in {bin_dir()}, but PATH finds {found} first', kind=Kind.NOT_ON_PATH)
    return Result(True, f'git {latest}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────


def place(binary: Path, executable: str) -> None:
    """Move one unpacked binary into `~/.local/bin` under the name it is called by."""
    destination = bin_dir() / executable
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(binary), destination)
    effects.make_executable(destination)


def confirm_on_path(what: str, executable: str) -> Result:
    """Everything above ends here: installed is a claim PATH has to agree with."""
    if not shutil.which(executable):
        return Result(False, f'{executable} installed but is not on PATH — is {bin_dir()} in it?', kind=Kind.NOT_ON_PATH)
    return Result(True, f'{what} installed', kind=Kind.APPLIED)


INSTALLERS: dict[str, Installer] = {
    'theme': checkout_tool,
    'font': checkout_tool,
    'zmk': checkout_tool,
    'bashselfupdate': bashselfupdate,
    'claude-code': claude_code,
    'awscli': awscli,
    'mount-s3': mount_s3,
    'terraform-ls': terraform_ls,
    'bats': bats,
    'git': git,
}
"""Which function installs which entry.

`validate.py` checks this against `packages.yml` in one direction and
`tests/install/test_custom_installers.py` in the other, so an entry nothing can
install and a function nothing declares are both errors rather than silence.
"""
