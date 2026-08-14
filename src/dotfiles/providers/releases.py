"""What each GitHub release publishes, and where its binary sits once unpacked.

One small function per tool, all in one file, so a new tool is a copy of the one
above it and every spelling is visible side by side. This is the part that stays
**code**, and moving it into `packages.yml` as data has been rejected twice —
no placeholder vocabulary survives contact with these:

    shellcheck   darwin.aarch64,  and a .tar.xz
    trivy        macOS-ARM64 / Linux-64bit
    zk           x86_64 on macOS, amd64 on Linux — the same CPU, spelled two ways
    fzf          darwin_arm64 but linux_amd64, in one name
    just         GNU triples; yazi the same triples but a .zip

`packages.yml` keeps only the declarative facts it already carries — `repo`,
`release_tag_prefix`, `min_version`, `binary_link` — and the rationale from
`docs/architecture/github-releases.md` § "Why asset naming is code"
holds identically in Python: URL patterns vary enough that a template becomes
complex, and inline keeps it explicit and traceable.

Each function takes the resolved tag and a `Target`, and returns an `ReleaseArtifact`. It
does not build a URL: the repo lives in the catalog and the tag is resolved
upstream, so a function that built its own URL would be a second place for the
host and the path shape to be wrong.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Callable

from dotfiles.coordinates import Target


class Archive(enum.StrEnum):
    """How the asset is packed, which decides how the binary is extracted."""

    TARBALL = 'tarball'
    ZIP = 'zip'
    GZIP = 'gzip'
    """A bare gzipped binary, not a tar. tree-sitter alone."""

    RAW = 'raw'
    """The binary itself, downloaded and chmod +x. hadolint, terraformer, yq."""


@dc.dataclass(frozen=True, slots=True)
class Companion:
    """A file fetched at the release's tag that the release does not publish.

    Not new vocabulary: the offline bundler already has this concept as
    `--print-extras`, because a companion has to be staged like any other
    download for a restricted network to install the tool at all.

    **The name is static and only the URL moves with the tag.** Keep it that way:
    the split is what lets a checker ask what should be on disk without resolving a
    release first, and resolving one costs a network round trip that
    `ghrelease.missing_companions` has to answer without.
    """

    name: str

    url_template: str
    """Where to fetch it, with `{tag}` standing in for the release it is paired with."""

    def url(self, tag: str) -> str:
        return self.url_template.format(tag=tag)


@dc.dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    """One release asset, and how to get a binary out of it."""

    name: str
    archive: Archive
    path: str = ''
    """Where the binary sits inside the archive, when it is not at the root."""

    extras: tuple[str, ...] = ()
    """Other binaries in the same archive, placed beside the first under their own names.

    Each is placed if present and passed over if not. That tolerance is tenv's:
    its set of proxy shims has grown release by release — atmos and terramate
    arrived after the others — so an install that demanded all of them would break
    on the release *before* the one that added a name, and one that demanded a
    fixed subset would silently stop installing whatever came next.
    """

    tree: bool = False
    """The archive installs as a directory under `~/.local`, not as loose binaries.

    neovim alone: `nvim` will not start without the runtime files packaged beside
    it, so `path` is then relative to `~/.local` and what lands in `~/.local/bin`
    is a symlink into the unpacked tree rather than a copy of one file out of it.
    """


def _bare(tag: str) -> str:
    """The version without its leading `v`.

    Most publishers name the asset after the bare version while tagging with the
    `v`, so this appears in most of the functions below and never in the tag.
    """
    return tag.removeprefix('v')


def expand_pattern(pattern: str, version: str, target: Target, *, asset_target: str = '', arch: str = '') -> str:
    """A declared `binary_pattern` filled in for one platform and version.

    The vocabulary the file above rejects, kept for the two sections that can use
    it. That is not a contradiction: the 23 release entries defeated a template
    because each publisher invented its own spelling, while `go_tools` and
    `cargo_packages` are named by GoReleaser and cargo-dist conventions that vary
    within a small fixed set. Where an upstream steps outside it, the declaration
    overrides the piece that differs rather than the whole name — which is what
    `linux_target` and `darwin_target` are.

    `arch` is a parameter because the two sections disagree about what `{arch}`
    means: cargo tools name arm64 assets `aarch64` and Go tools do not. Passing
    the spelling from the caller keeps that a fact about each section rather than
    a branch in here that has to know who is asking.
    """
    replacements = {
        '{version}': version,
        '{version_num}': version.lstrip('v'),
        '{target}': asset_target,
        '{os}': str(target.os_family),
        '{arch}': arch or str(target.arch),
        '{go_arch}': 'arm64' if target.is_arm else 'amd64',
        '{Os}': 'Darwin' if target.is_darwin else 'Linux',
        '{Arch}': str(target.arch),
        '{os_mac}': 'macOS' if target.is_darwin else 'linux',
        '{Os_mac}': 'macOS' if target.is_darwin else 'Linux',
        '{platform}': 'apple_darwin' if target.is_darwin else 'linux',
    }
    expanded = pattern
    for placeholder, value in replacements.items():
        expanded = expanded.replace(placeholder, value)
    return expanded


# ─────────────────────────────────────────────────────────────────────────────
# The tools
# ─────────────────────────────────────────────────────────────────────────────


def atuin(tag: str, target: Target) -> ReleaseArtifact:
    """musl for both architectures, and no darwin spelling: atuin is declared on
    Linux only, which is why the arm target is still a linux triple."""
    triple = 'aarch64-unknown-linux-musl' if target.is_arm else 'x86_64-unknown-linux-musl'
    return ReleaseArtifact(f'atuin-{triple}.tar.gz', Archive.TARBALL, path=f'atuin-{triple}/atuin')


def duckdb(tag: str, target: Target) -> ReleaseArtifact:
    """The one entry here whose architecture is spelled the same on both systems,
    so only the OS stem moves. `osx-universal` is also published and was rejected:
    it is the two binaries in one file, 34MB against 18MB, to dodge a branch every
    other entry already carries and that `Target` exists to answer."""
    system = 'osx' if target.is_darwin else 'linux'
    arch = 'arm64' if target.is_arm else 'amd64'
    return ReleaseArtifact(f'duckdb_cli-{system}-{arch}.zip', Archive.ZIP, path='duckdb')


def duf(tag: str, target: Target) -> ReleaseArtifact:
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_x86_64') if target.is_darwin else 'linux_x86_64'
    return ReleaseArtifact(f'duf_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='duf')


def fzf(tag: str, target: Target) -> ReleaseArtifact:
    """arm64 on darwin against amd64 on linux, in one name.

    Its `fzf-tmux` companion is declared in `COMPANIONS` rather than here, because
    it is not part of the release this names.
    """
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_amd64') if target.is_darwin else 'linux_amd64'
    return ReleaseArtifact(f'fzf-{_bare(tag)}-{suffix}.tar.gz', Archive.TARBALL, path='fzf')


def glow(tag: str, target: Target) -> ReleaseArtifact:
    """Nested under a directory named after the archive, on both platforms.

    It was flat until v2, and the entry read `path='glow'` until the tarball
    stopped having a `glow` at its root — verified against 2.1.2 on Linux and
    Darwin, both `glow_<version>_<suffix>/glow`. This is the drift
    `tests/install/test_release_urls.py` exists to catch and cannot: it checks that
    the release publishes the asset, not what is inside it.
    """
    suffix = ('Darwin_arm64' if target.is_arm else 'Darwin_x86_64') if target.is_darwin else 'Linux_x86_64'
    stem = f'glow_{_bare(tag)}_{suffix}'
    return ReleaseArtifact(f'{stem}.tar.gz', Archive.TARBALL, path=f'{stem}/glow')


def hadolint(tag: str, target: Target) -> ReleaseArtifact:
    """Ships the binary itself, and is the one tool naming arm on Linux."""
    if target.is_darwin:
        suffix = 'macos-arm64' if target.is_arm else 'macos-x86_64'
    else:
        suffix = 'linux-arm64' if target.is_arm else 'linux-x86_64'
    return ReleaseArtifact(f'hadolint-{suffix}', Archive.RAW)


def just(tag: str, target: Target) -> ReleaseArtifact:
    """Named after the tag as published, `v` and all — unlike almost every other."""
    if target.is_darwin:
        triple = 'aarch64-apple-darwin' if target.is_arm else 'x86_64-apple-darwin'
    else:
        triple = 'x86_64-unknown-linux-musl'
    return ReleaseArtifact(f'just-{tag}-{triple}.tar.gz', Archive.TARBALL, path='just')


def lazygit(tag: str, target: Target) -> ReleaseArtifact:
    """Lowercase `linux_x86_64`. It was fetched as `Linux_x86_64` for a while and
    downloaded fine, because GitHub resolves asset paths case-insensitively —
    which then missed the checksum entry recorded under the real name."""
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_x86_64') if target.is_darwin else 'linux_x86_64'
    return ReleaseArtifact(f'lazygit_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='lazygit')


def neovim(tag: str, target: Target) -> ReleaseArtifact:
    """Installs a tree rather than a binary: `bin/nvim` plus its runtime."""
    if target.is_darwin:
        stem = 'nvim-macos-arm64' if target.is_arm else 'nvim-macos-x86_64'
    else:
        stem = 'nvim-linux-x86_64'
    return ReleaseArtifact(f'{stem}.tar.gz', Archive.TARBALL, path=f'{stem}/bin/nvim', tree=True)


def ntfy(tag: str, target: Target) -> ReleaseArtifact:
    """One universal `darwin_all` asset, so darwin is the only entry here that does
    not branch on `is_arm` — an Apple Silicon box and an Intel one fetch the same
    file. Linux still splits, and the binary sits under a stem directory.
    """
    suffix = 'darwin_all' if target.is_darwin else ('linux_arm64' if target.is_arm else 'linux_amd64')
    stem = f'ntfy_{_bare(tag)}_{suffix}'
    return ReleaseArtifact(f'{stem}.tar.gz', Archive.TARBALL, path=f'{stem}/ntfy')


def shellcheck(tag: str, target: Target) -> ReleaseArtifact:
    """`aarch64` where everything else says arm64, dots where everything else
    says dashes, and the only `.tar.xz` in the set."""
    if target.is_darwin:
        suffix = 'darwin.aarch64' if target.is_arm else 'darwin.x86_64'
    else:
        suffix = 'linux.x86_64'
    return ReleaseArtifact(f'shellcheck-{tag}.{suffix}.tar.xz', Archive.TARBALL, path=f'shellcheck-{tag}/shellcheck')


TENV_PROXIES = ('terraform', 'tofu', 'terragrunt', 'terramate', 'atmos', 'tf')
"""The shims tenv ships beside itself, each dispatching to the version it manages.

`terraform` on PATH being one of these is the whole point of installing tenv: it
is what makes a `.terraform-version` file decide which binary runs.
"""


def tenv(tag: str, target: Target) -> ReleaseArtifact:
    """Keeps the `v` in the asset name, and capitalises the platform."""
    platform_name = 'Darwin' if target.is_darwin else 'Linux'
    arch = 'arm64' if target.is_arm else 'x86_64'
    return ReleaseArtifact(f'tenv_{tag}_{platform_name}_{arch}.tar.gz', Archive.TARBALL, path='tenv', extras=TENV_PROXIES)


def terraformer(tag: str, target: Target) -> ReleaseArtifact:
    """`all` is the provider bundle; the per-provider builds are not what is declared."""
    if target.is_darwin:
        suffix = 'darwin-arm64' if target.is_arm else 'darwin-amd64'
    else:
        suffix = 'linux-amd64'
    return ReleaseArtifact(f'terraformer-all-{suffix}', Archive.RAW)


def terrascan(tag: str, target: Target) -> ReleaseArtifact:
    arch = ('arm64' if target.is_arm else 'x86_64') if target.is_darwin else 'x86_64'
    platform_name = 'Darwin' if target.is_darwin else 'Linux'
    return ReleaseArtifact(f'terrascan_{_bare(tag)}_{platform_name}_{arch}.tar.gz', Archive.TARBALL, path='terrascan')


def tflint(tag: str, target: Target) -> ReleaseArtifact:
    """The asset carries no version at all, so the tag appears only in the path."""
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_amd64') if target.is_darwin else 'linux_amd64'
    return ReleaseArtifact(f'tflint_{suffix}.zip', Archive.ZIP, path='tflint')


def tree_sitter(tag: str, target: Target) -> ReleaseArtifact:
    """`x64`, not `x86_64` or `amd64`, and a bare gzip rather than a tarball."""
    if target.is_darwin:
        suffix = 'macos-arm64' if target.is_arm else 'macos-x64'
    else:
        suffix = 'linux-x64'
    return ReleaseArtifact(f'tree-sitter-{suffix}.gz', Archive.GZIP)


def trivy(tag: str, target: Target) -> ReleaseArtifact:
    """`macOS-ARM64` and `Linux-64bit`: capitalisation and a bit-width, unique here."""
    if target.is_darwin:
        suffix = 'macOS-ARM64' if target.is_arm else 'macOS-64bit'
    else:
        suffix = 'Linux-64bit'
    return ReleaseArtifact(f'trivy_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='trivy')


def win32yank(tag: str, target: Target) -> ReleaseArtifact:
    """One asset for every target, because it is a Windows binary reached from WSL."""
    return ReleaseArtifact('win32yank-x64.zip', Archive.ZIP, path='win32yank.exe')


def yazi(tag: str, target: Target) -> ReleaseArtifact:
    """GNU triples like `just`, but a zip, and gnu rather than musl on Linux.

    `ya` is yazi's own package manager and ships beside the binary, but nothing
    here calls it: the plugins are declared in `packages.yml` under
    `yazi_plugins` and cloned by the plugins resource, four stages later. `ya pkg
    add` ran from this install once, six stages before the symlink pass, and
    wrote its state file to a path this repo also deployed to.
    """
    if target.is_darwin:
        triple = 'aarch64-apple-darwin' if target.is_arm else 'x86_64-apple-darwin'
    else:
        triple = 'x86_64-unknown-linux-gnu'
    return ReleaseArtifact(f'yazi-{triple}.zip', Archive.ZIP, path=f'yazi-{triple}/yazi', extras=(f'yazi-{triple}/ya',))


def yq(tag: str, target: Target) -> ReleaseArtifact:
    """Go arch, a bare binary, and the one release publishing a checksums file its
    own asset cannot be found in — see `PUBLISHES_NO_CHECKSUM` in the corpus test."""
    arch = 'arm64' if target.is_arm else 'amd64'
    os_name = 'darwin' if target.is_darwin else 'linux'
    return ReleaseArtifact(f'yq_{os_name}_{arch}', Archive.RAW)


def zk(tag: str, target: Target) -> ReleaseArtifact:
    """Spells the same CPU two ways depending on the OS — `x86_64` on macOS and
    `amd64` on Linux. This is the entry that defeats a flat placeholder outright."""
    if target.is_darwin:
        platform_name, arch = 'macos', ('arm64' if target.is_arm else 'x86_64')
    else:
        platform_name, arch = 'linux', 'amd64'
    return ReleaseArtifact(f'zk-{tag}-{platform_name}-{arch}.tar.gz', Archive.TARBALL, path='zk')


def _go_release_cli(binary: str) -> Callable[[str, Target], ReleaseArtifact]:
    """The four private data CLIs, which are goreleaser builds in monorepos.

    Their tag carries a `cli/` prefix because the same repo releases an API and a
    web app, so the version in the asset name is the tag with that prefix and the
    `v` both removed.
    """

    def build(tag: str, target: Target) -> ReleaseArtifact:
        version = _bare(tag.rsplit('/', 1)[-1])
        os_name = 'darwin' if target.is_darwin else 'linux'
        arch = 'arm64' if target.is_arm else 'amd64'
        return ReleaseArtifact(f'{binary}_{version}_{os_name}_{arch}.tar.gz', Archive.TARBALL, path=binary)

    return build


ASSETS: dict[str, Callable[[str, Target], ReleaseArtifact]] = {
    'atuin': atuin,
    'duckdb': duckdb,
    'duf': duf,
    'fzf': fzf,
    'glow': glow,
    'hadolint': hadolint,
    'icb': _go_release_cli('icb'),
    'just': just,
    'lazygit': lazygit,
    'learning': _go_release_cli('learning'),
    'meso': _go_release_cli('meso'),
    'neovim': neovim,
    'nomad': _go_release_cli('nomad'),
    'ntfy': ntfy,
    'shellcheck': shellcheck,
    'tenv': tenv,
    'terraformer': terraformer,
    'terrascan': terrascan,
    'tflint': tflint,
    'tree-sitter': tree_sitter,
    'trivy': trivy,
    'win32yank': win32yank,
    'yazi': yazi,
    'yq': yq,
    'zk': zk,
}
"""Keyed by the `packages.yml` entry name, which is what a manifest declares.

`tests/install/test_release_urls.py` asserts this covers every declared release
and that each function names the asset the release actually publishes.
"""

COMPANIONS: dict[str, tuple[Companion, ...]] = {
    'fzf': (Companion('fzf-tmux', 'https://raw.githubusercontent.com/junegunn/fzf/{tag}/bin/fzf-tmux'),),
}
"""Files that ship *with* a tool without being in its release, by entry name.

Its own table rather than a field on `ReleaseArtifact`, because a companion is not part of
the release the asset function describes and does not depend on the tag or the
target the way an asset name does. Separating them is what makes a companion
*observable*: `dotfiles check` can ask what fzf owes without resolving a release,
where reading it off a `ReleaseArtifact` needed a tag and therefore a network call.

Nothing else on disk says a companion is owed, which is why reading it from here
is what lets `check` see one is gone: fzf installs cleanly without `fzf-tmux` and
the tmux popup binding then silently does nothing, surfacing days later at a
keystroke rather than in any verdict.
"""


def asset_url(repo: str, tag: str, asset: ReleaseArtifact) -> str:
    """The browser download URL. Private repos need the asset-id endpoint instead,
    which `github_release.download_asset` falls back to on its own."""
    return f'https://github.com/{repo}/releases/download/{tag}/{asset.name}'
