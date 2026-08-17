# Restricted Networks

The work machine sits behind a firewall that blocks most of what an install
reaches for. Everything here is built for that machine, and none of it is proxy
or registry-mirror configuration.

## Find out what is actually blocked

`dotfiles network check` walks every URL the install touches and reports a
pass/fail line per host. Run it on the restricted machine first: the answer is
rarely "the internet is blocked" and usually "GitHub release assets are blocked
but the API is not", which changes what you need to carry in.

Pass `--output <path>` to record the run somewhere outside the repo. `--output`
has no default on purpose, and the results never belong in version control: a
recorded verdict is one machine's answer on one day, and it can only be re-taken
from that same network, so it goes stale where nothing can refresh it. Keep it
under `$XDG_STATE_HOME` if you want to diff two runs after the rules change.
`tests/install/test_network.py` fails the suite if a measurement is ever tracked.

Note what the run itself looks like from the other side. It is a burst of
requests to distinct external hosts, and it classifies TLS interception, so it
reads as egress mapping to anything watching. Run it once when you need the
answer, not on a schedule.

## Install without the network

`dotfiles bundle create` downloads every GitHub release binary, cargo binary and
install script into a single tarball, on a machine that *has* the network. It
builds for a machine that is deliberately not the one running it.
`dotfiles bundle create --help` says what that means for each flag.

It also carries what the bootstrap itself needs before any of that can run: the
`uv` binary for the target platform, and a wheelhouse holding the CLI's whole
dependency closure. Without those the restricted machine can unpack a bundle it
has no way to install from, which is the one failure the bundle exists to
prevent. The wheels cover every CPython at or above this package's
`requires-python`, because which interpreter the target has is a fact only the
target knows.

The tarball is named after a UTC stamp, the manifest and the target platform, so
handing it to something else means retyping a name that changes every build.
`dotfiles bundle upload` finds the newest one itself, which is why the handoff is
two commands rather than a substitution:

```bash
dotfiles bundle create --machine wsl-work-workstation --arch x86_64
dotfiles bundle upload
```

`--print-path` still writes the finished path to stdout for anything else that
wants it. The build log is unaffected — it goes to stderr either way — and the
path is printed only after the cache prune finishes, so nothing downstream sees a
bundle that is still being written.

`dotfiles remote check` answers whether the upload has anywhere to go. It
measures the listing rather than inferring it from `command -v`, because a box
with the binary and no credential answers that perfectly and fails at the first
upload. `docs/architecture/offline-bundles.md` holds the transport config shape
and why it is that shape.

## Carry only what changed

`dotfiles status upload` publishes what this machine already has, scoped to
packages and toolchains and to nothing else. Then, where the network is:

```bash
dotfiles bundle create --machine wsl-work-workstation --arch x86_64 --against latest
dotfiles bundle upload
```

Every tool the status reports at the version upstream currently publishes is left
out, and recorded in the bundle as measured rather than missing. The work box
reads that as up to date instead of unmeasurable, and a tool in neither place is
still reported as one nothing has ever measured.

Two config keys close the loop without a command: `fetch_bundle_when_none_is_staged`
and `publish_status_after_offline_apply`. Both default off, deliberately — the
concern on that network is monitoring rather than capability, so a converge that
reaches a server unasked is a change in posture rather than a convenience.

**Nothing but packages and versions leaves that machine.** The document is
composed over an allowlist of resources, and the bytes are read for this machine's
hostname and account before any of them move. A row carrying one of those names is
withheld and named on screen rather than refusing the whole document — a tool's own
version banner can relay a hostname it got from somewhere else, and refusing for
one row took the return leg off a working machine. Both guards, why there are two,
and why the row is the unit are in `docs/architecture/offline-bundles.md`.

The builder is `src/dotfiles/create_bundle.py`. It was shell until the naming
above proved the problem — a bash function has no return value, so "produce a
tarball and tell the caller its name" has no direct expression there. Its logic
— checksum parsing, cache keys, wheel tag matching, archive repackaging — is
covered by `tests/install/test_create_bundle.py`, which needs neither a network
nor a container and runs in well under a second.

On a machine with no CLI yet, `./install.sh --machine NAME --offline` finds the
newest archive in the download cache, beside the checkout or in `$HOME`, unpacks
it into `$XDG_CACHE_HOME/dotfiles/staged/<archive name>/`, installs uv and the CLI
from it with no index at all, and prints the `dotfiles apply --machine NAME
--offline` that installs the machine from it. The flag is needed on both, and for
different reasons: it says where the bootstrap gets uv and the wheels, and it
says the apply installs from a staged bundle rather than from the network.

On a machine that already has the CLI, the bootstrap is not the way to unpack a
newer bundle — `dotfiles bundle stage` does that alone, and the apply does it
unasked when it finds nothing staged.

Each bundle keeps its own directory rather than merging into one. The newest
carrying a file answers for it and an older one still answers for the rest, which
is what lets a sparse bundle carry only what changed. `dotfiles bundle prune`
sweeps what is past the retention limit, and its help says which bundles are
pinned against that limit and what sweeping one would cost.

This path is tested end to end by `uv run pytest tests/e2e --docker -k offline`:
it builds a bundle, starts a container blackholed to a declared set of hosts, and
asserts the install completes from cache. If you change the bundle format, that is
what catches it.

The blocklist is declared in `tests/e2e/harness.py` as `BLOCKED_HOSTS` and
everything else the plan reaches stays resolvable, so the rig needs no record of
any real network. It asserts both halves — that the blocked hosts really are
unreachable, and that the reachable ones really are. Asserting only the blocked
half let the rig drift stricter than intended: it blackholed `github.com`
outright, so theme, font and bashselfupdate failed to clone in a rehearsal of a
network where they clone fine, and the log read as though the bundle had a gap it
does not have.

## Windows tools when winget is blocked

The bundle carries them, the same way it carries every other category.

Each `winget_packages` row in `install/packages.yml` names a GitHub repo and
asset alongside the Store id, so a row is installable two ways from one
declaration. `bundle create --machine windows-work-workstation` stages the `.exe`
from the release and verifies it against the published checksum, and the provider
reads the staged binary rather than reaching the Store.

It falls back to the bundle when a bundle is present, rather than only under
`--offline`. Reaching a network is not the same as reaching the Store on that
box — winget is blocked there while `github.com` is not — so a run that has bytes
staged uses them whichever way it was invoked.

Several of those projects publish no Windows checksum at all. That is stated per
tool rather than passed over, so what was and was not verified stays visible in
the build output.

**Bootstrapping that box runs from the bundle too.** `install.sh` reads
`uname -s`, answers `uv.exe` under Git Bash, and copies `$BUNDLE/bin/uv.exe` onto
PATH, which is the name a Windows bundle stages. With a network but no bundle it
runs astral's PowerShell installer; the sh one is not a fallback there, because it
fetches a Linux binary Git Bash will copy into place and then fail to run. See
`docs/reference/rebuilding-a-machine.md` for what a first install needs.

## Why the Neovim setup does not need any of this

Neovim uses native LSP rather than Mason, so opening an editor does not reach
`raw.githubusercontent.com` at all. Language servers arrive through
`npm_globals` and `uv_tools` in `install/packages.yml` like every other tool,
which means the bundle above already carries them. There is nothing
Neovim-specific to arrange.
