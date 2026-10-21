"""Which items install from the staged bundle, and which from the network.

A network that refuses some hosts names them in this tool's config, under
`[network] blocked`. An item whose download reaches one of them installs from the
staged bundle. Everything else installs from the network, as it would anywhere.

Each item reaches two kinds of host, and they are routed apart. Its version check
asks one, and its download fetches from another. A release tool on a network that
refuses GitHub's asset hosts still answers its version through `api.github.com`,
so it is measured against the newest release while its bytes come from the bundle.

`--offline` keeps the list. Where none is declared, or the declared one is empty,
it counts every host as blocked, so a run takes everything from the bundle and
asks no network at all.

Which hosts each item reaches is `registry.Provider.hosts`, one method per
provider. `dotfiles network check` reads the same answer, so the routing and the
measurement of the network cannot name different hosts for one item.
"""

from __future__ import annotations

import dataclasses as dc
import re
import tomllib
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit

from dotfiles import paths
from dotfiles import settings

TABLE = 'network'
KEY = 'blocked'

GITHUB = 'github.com'
GITHUB_API = 'api.github.com'
GITHUB_RAW = 'raw.githubusercontent.com'

GITHUB_ASSET_HOSTS = frozenset(
    {
        'release-assets.githubusercontent.com',
        'objects.githubusercontent.com',
        'github-releases.githubusercontent.com',
    }
)
"""Where github.com redirects a release download.

A firewall that refuses these refuses every release asset while github.com still
serves clones and the API, which is the shape of the network this module exists for.
"""

RELEASE_DOWNLOAD = frozenset({GITHUB, *GITHUB_ASSET_HOSTS})

CRATES_IO = 'crates.io'
GO_PROXY = 'proxy.golang.org'
GO_DOWNLOADS = 'dl.google.com'
"""Where go.dev redirects a toolchain tarball."""
NPM_REGISTRY = 'registry.npmjs.org'
PYPI = frozenset({'pypi.org', 'files.pythonhosted.org'})
RUST_DIST = 'static.rust-lang.org'
"""Where rustup downloads the toolchain its script installs."""
NODEJS = 'nodejs.org'

HOSTNAME = re.compile(r'^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


def hostname(value: object) -> bool:
    """Whether a `blocked` entry is a hostname, as against a URL or a pattern."""
    return isinstance(value, str) and bool(HOSTNAME.match(value))


def host_of(url: str) -> str:
    """The host a URL reaches, or '' for one that names none."""
    return urlsplit(url if '//' in url else f'https://{url}').hostname or ''


def hosts_of(urls: Iterable[str]) -> frozenset[str]:
    return frozenset(filter(None, map(host_of, urls)))


@dc.dataclass(frozen=True, slots=True)
class ItemHosts:
    """The hosts one item's version check asks, and the hosts its download fetches from."""

    version: frozenset[str] = frozenset()
    download: frozenset[str] = frozenset()

    @property
    def every(self) -> frozenset[str]:
        return self.version | self.download


NONE = ItemHosts()


@dc.dataclass(frozen=True, slots=True)
class Route:
    """Where one item's version and bytes come from on this run."""

    bundled: bool
    """The download reaches a blocked host, so the item installs from the staged bundle."""

    measured: bool
    """The version check reaches no blocked host, so currency is asked of upstream."""

    blocking: tuple[str, ...] = ()
    """The blocked hosts this item reaches, for the row that names why."""

    everything: bool = False

    @property
    def because(self) -> str:
        """Why this item cannot reach the network, as a clause for its row."""
        if self.everything:
            return 'this --offline run declares no blocked hosts, so it reaches no network'
        if not self.blocking:
            return ''
        named = [host for host in self.blocking if host not in GITHUB_ASSET_HOSTS]
        if len(named) < len(self.blocking):
            named.insert(0, "GitHub's release-asset hosts")
        verb = 'is' if len(self.blocking) == 1 else 'are'
        return f'{" and ".join(named)} {verb} blocked'


NETWORK = Route(bundled=False, measured=True)


@dc.dataclass(frozen=True, slots=True)
class Routes:
    """This run's blocked hosts, read once and asked per item."""

    blocked: frozenset[str] = frozenset()

    everything: bool = False
    """Every host counts as blocked: `--offline` with no blocked hosts declared."""

    offline: bool = False
    """`--offline` was passed, so this run contacts no remote."""

    source: str = ''
    """The config file the list came from, `~`-rooted, or '' where none declared one."""

    @property
    def restricts(self) -> bool:
        """Whether any item on this run can be routed to the bundle."""
        return self.everything or bool(self.blocked)

    def reaches(self, hosts: Iterable[str]) -> bool:
        """Whether every one of these hosts answers on this run."""
        return not self.everything and not (self.blocked & frozenset(hosts))

    def route(self, hosts: ItemHosts) -> Route:
        """Where an item reaching these hosts takes its version and its bytes from."""
        if not self.restricts:
            return NETWORK
        blocking = tuple(sorted(hosts.every if self.everything else hosts.every & self.blocked))
        return Route(
            bundled=not self.reaches(hosts.download) if hosts.download else self.everything,
            measured=self.reaches(hosts.version) if hosts.version else not self.everything,
            blocking=blocking,
            everything=self.everything,
        )

    def opening(self) -> str:
        """What this run's routing is, for the line an apply opens with."""
        if self.everything:
            return '--offline, and no blocked hosts are declared, so every host counts as blocked'
        if not self.blocked:
            return ''
        count = len(self.blocked)
        hosts = f'{count} host{"" if count == 1 else "s"}'
        return f'this network blocks {hosts}, from {self.source}'


def declared_in(path: Path) -> frozenset[str] | None:
    """The hosts a config file declares blocked, or None where it declares no list.

    An entry that is not a hostname is dropped. `validate.network_declared` reports it
    for the repo's copies, and a hand-edited file is answered by `dotfiles config show`.
    """
    try:
        table = tomllib.loads(path.read_text()).get(TABLE)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    listed = table.get(KEY) if isinstance(table, dict) else None
    if not isinstance(listed, list):
        return None
    return frozenset(host for host in listed if hostname(host))


def trust_copy(repo: Path, trust: object) -> Path:
    """The config file the symlink stage deploys to a machine of this network trust."""
    return repo / 'configs' / 'trust' / str(trust) / '.config' / 'dotfiles' / 'config.toml'


def read(*, offline: bool, declared_at: Path | None = None) -> Routes:
    """This machine's routes, from its own config or the copy its symlinks deploy.

    The deployed file answers first, because it is the machine's own. A fresh machine
    has none until the symlink stage of its first apply, so `declared_at` names the
    copy that stage will deploy, and the first apply routes by it.
    """
    for candidate in (settings.config_file(), declared_at):
        if candidate is None or not candidate.is_file():
            continue
        found = declared_in(candidate)
        if found is not None:
            return Routes(blocked=found, everything=offline and not found, offline=offline, source=paths.under_home(candidate))
    return Routes(everything=offline, offline=offline)
