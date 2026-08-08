"""What each GitHub release publishes, and where its binary sits once unpacked.

Twenty-three small functions, all in one file, so a new tool is a copy of the one
above it and every spelling is visible side by side. This is the part that stays
**code** — measured across all 23 on 2026-08-07 and rejected as `packages.yml`
data twice, because no placeholder vocabulary survives contact with them:

    shellcheck   darwin.aarch64,  and a .tar.xz
    trivy        macOS-ARM64 / Linux-64bit
    zk           x86_64 on macOS, amd64 on Linux — the same CPU, spelled two ways
    fzf          darwin_arm64 but linux_amd64, in one name
    just         GNU triples; yazi the same triples but a .zip

`packages.yml` keeps only the declarative facts it already carries — `repo`,
`release_tag_prefix`, `min_version`, `binary_link` — and the rationale from
`docs/architecture/github-release-installer.md` § "Why Not More Abstraction?"
holds identically in Python: URL patterns vary enough that a template becomes
complex, and inline keeps it explicit and traceable.

Each function takes the resolved tag and a `Target`, and returns an `Asset`. It
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
class Asset:
    """One release asset, and how to get a binary out of it."""

    name: str
    archive: Archive
    path: str = ''
    """Where the binary sits inside the archive, when it is not at the root."""


def _bare(tag: str) -> str:
    """The version without its leading `v`.

    Most publishers name the asset after the bare version while tagging with the
    `v`, so this appears in most of the functions below and never in the tag.
    """
    return tag.removeprefix('v')


# ─────────────────────────────────────────────────────────────────────────────
# The tools
# ─────────────────────────────────────────────────────────────────────────────


def atuin(tag: str, target: Target) -> Asset:
    """musl for both architectures, and no darwin spelling: atuin is declared on
    Linux only, which is why the arm target is still a linux triple."""
    triple = 'aarch64-unknown-linux-musl' if target.is_arm else 'x86_64-unknown-linux-musl'
    return Asset(f'atuin-{triple}.tar.gz', Archive.TARBALL, path=f'atuin-{triple}/atuin')


def duf(tag: str, target: Target) -> Asset:
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_x86_64') if target.is_darwin else 'linux_x86_64'
    return Asset(f'duf_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='duf')


def fzf(tag: str, target: Target) -> Asset:
    """arm64 on darwin against amd64 on linux, in one name."""
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_amd64') if target.is_darwin else 'linux_amd64'
    return Asset(f'fzf-{_bare(tag)}-{suffix}.tar.gz', Archive.TARBALL, path='fzf')


def glow(tag: str, target: Target) -> Asset:
    suffix = ('Darwin_arm64' if target.is_arm else 'Darwin_x86_64') if target.is_darwin else 'Linux_x86_64'
    return Asset(f'glow_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='glow')


def hadolint(tag: str, target: Target) -> Asset:
    """Ships the binary itself, and is the one tool naming arm on Linux."""
    if target.is_darwin:
        suffix = 'macos-arm64' if target.is_arm else 'macos-x86_64'
    else:
        suffix = 'linux-arm64' if target.is_arm else 'linux-x86_64'
    return Asset(f'hadolint-{suffix}', Archive.RAW)


def just(tag: str, target: Target) -> Asset:
    """Named after the tag as published, `v` and all — unlike almost every other."""
    if target.is_darwin:
        triple = 'aarch64-apple-darwin' if target.is_arm else 'x86_64-apple-darwin'
    else:
        triple = 'x86_64-unknown-linux-musl'
    return Asset(f'just-{tag}-{triple}.tar.gz', Archive.TARBALL, path='just')


def lazygit(tag: str, target: Target) -> Asset:
    """Lowercase `linux_x86_64`. It was fetched as `Linux_x86_64` for a while and
    downloaded fine, because GitHub resolves asset paths case-insensitively —
    which then missed the checksum entry recorded under the real name."""
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_x86_64') if target.is_darwin else 'linux_x86_64'
    return Asset(f'lazygit_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='lazygit')


def neovim(tag: str, target: Target) -> Asset:
    """Installs a tree rather than a binary: `bin/nvim` plus its runtime."""
    if target.is_darwin:
        stem = 'nvim-macos-arm64' if target.is_arm else 'nvim-macos-x86_64'
    else:
        stem = 'nvim-linux-x86_64'
    return Asset(f'{stem}.tar.gz', Archive.TARBALL, path=f'{stem}/bin/nvim')


def shellcheck(tag: str, target: Target) -> Asset:
    """`aarch64` where everything else says arm64, dots where everything else
    says dashes, and the only `.tar.xz` in the set."""
    if target.is_darwin:
        suffix = 'darwin.aarch64' if target.is_arm else 'darwin.x86_64'
    else:
        suffix = 'linux.x86_64'
    return Asset(f'shellcheck-{tag}.{suffix}.tar.xz', Archive.TARBALL, path=f'shellcheck-{tag}/shellcheck')


def tenv(tag: str, target: Target) -> Asset:
    """Keeps the `v` in the asset name, and capitalises the platform."""
    platform_name = 'Darwin' if target.is_darwin else 'Linux'
    arch = 'arm64' if target.is_arm else 'x86_64'
    return Asset(f'tenv_{tag}_{platform_name}_{arch}.tar.gz', Archive.TARBALL, path='tenv')


def terraformer(tag: str, target: Target) -> Asset:
    """`all` is the provider bundle; the per-provider builds are not what is declared."""
    if target.is_darwin:
        suffix = 'darwin-arm64' if target.is_arm else 'darwin-amd64'
    else:
        suffix = 'linux-amd64'
    return Asset(f'terraformer-all-{suffix}', Archive.RAW)


def terrascan(tag: str, target: Target) -> Asset:
    arch = ('arm64' if target.is_arm else 'x86_64') if target.is_darwin else 'x86_64'
    platform_name = 'Darwin' if target.is_darwin else 'Linux'
    return Asset(f'terrascan_{_bare(tag)}_{platform_name}_{arch}.tar.gz', Archive.TARBALL, path='terrascan')


def tflint(tag: str, target: Target) -> Asset:
    """The asset carries no version at all, so the tag appears only in the path."""
    suffix = ('darwin_arm64' if target.is_arm else 'darwin_amd64') if target.is_darwin else 'linux_amd64'
    return Asset(f'tflint_{suffix}.zip', Archive.ZIP, path='tflint')


def tree_sitter(tag: str, target: Target) -> Asset:
    """`x64`, not `x86_64` or `amd64`, and a bare gzip rather than a tarball."""
    if target.is_darwin:
        suffix = 'macos-arm64' if target.is_arm else 'macos-x64'
    else:
        suffix = 'linux-x64'
    return Asset(f'tree-sitter-{suffix}.gz', Archive.GZIP)


def trivy(tag: str, target: Target) -> Asset:
    """`macOS-ARM64` and `Linux-64bit`: capitalisation and a bit-width, unique here."""
    if target.is_darwin:
        suffix = 'macOS-ARM64' if target.is_arm else 'macOS-64bit'
    else:
        suffix = 'Linux-64bit'
    return Asset(f'trivy_{_bare(tag)}_{suffix}.tar.gz', Archive.TARBALL, path='trivy')


def win32yank(tag: str, target: Target) -> Asset:
    """One asset for every target, because it is a Windows binary reached from WSL."""
    return Asset('win32yank-x64.zip', Archive.ZIP, path='win32yank.exe')


def yazi(tag: str, target: Target) -> Asset:
    """GNU triples like `just`, but a zip, and gnu rather than musl on Linux."""
    if target.is_darwin:
        triple = 'aarch64-apple-darwin' if target.is_arm else 'x86_64-apple-darwin'
    else:
        triple = 'x86_64-unknown-linux-gnu'
    return Asset(f'yazi-{triple}.zip', Archive.ZIP, path=f'yazi-{triple}/yazi')


def yq(tag: str, target: Target) -> Asset:
    """Go arch, a bare binary, and the one release publishing a checksums file its
    own asset cannot be found in — see `PUBLISHES_NO_CHECKSUM` in the corpus test."""
    arch = 'arm64' if target.is_arm else 'amd64'
    os_name = 'darwin' if target.is_darwin else 'linux'
    return Asset(f'yq_{os_name}_{arch}', Archive.RAW)


def zk(tag: str, target: Target) -> Asset:
    """Spells the same CPU two ways depending on the OS — `x86_64` on macOS and
    `amd64` on Linux. This is the entry that defeats a flat placeholder outright."""
    if target.is_darwin:
        platform_name, arch = 'macos', ('arm64' if target.is_arm else 'x86_64')
    else:
        platform_name, arch = 'linux', 'amd64'
    return Asset(f'zk-{tag}-{platform_name}-{arch}.tar.gz', Archive.TARBALL, path='zk')


def _go_release_cli(binary: str) -> Callable[[str, Target], Asset]:
    """The four private data CLIs, which are goreleaser builds in monorepos.

    Their tag carries a `cli/` prefix because the same repo releases an API and a
    web app, so the version in the asset name is the tag with that prefix and the
    `v` both removed.
    """

    def build(tag: str, target: Target) -> Asset:
        version = _bare(tag.rsplit('/', 1)[-1])
        os_name = 'darwin' if target.is_darwin else 'linux'
        arch = 'arm64' if target.is_arm else 'amd64'
        return Asset(f'{binary}_{version}_{os_name}_{arch}.tar.gz', Archive.TARBALL, path=binary)

    return build


ASSETS: dict[str, Callable[[str, Target], Asset]] = {
    'atuin': atuin,
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


def asset_url(repo: str, tag: str, asset: Asset) -> str:
    """The browser download URL. Private repos need the asset-id endpoint instead,
    which `github_release.download_asset` falls back to on its own."""
    return f'https://github.com/{repo}/releases/download/{tag}/{asset.name}'
