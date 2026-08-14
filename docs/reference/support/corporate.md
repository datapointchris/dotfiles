# Restricted Networks

The work machine sits behind a firewall that blocks most of what an install
reaches for. Three pieces of machinery exist for it, and none of them are the
generic advice about proxies and registry mirrors — that was the previous
content of this page, and it described an installer this repo does not use.

## Find out what is actually blocked

`dotfiles network check` walks every URL the install touches and reports a
pass/fail line per host. Run it on the restricted machine first: the answer is
rarely "the internet is blocked" and usually "GitHub release assets are blocked
but the API is not", which changes what you need to carry in.

Pass `--output install/offline/connectivity-results.txt` to record the run there.
That path is named rather than defaulted on purpose — every unfirewalled machine
finds everything reachable, so a default would let a check run anywhere replace
the one record of what work actually blocks.

The results file is committed deliberately. It is a record of one network's
behaviour at one time, which is the only way to compare against it after the
firewall rules change.

## Install without the network

`dotfiles bundle create` downloads every GitHub release binary, cargo binary and
install script into a single tarball, on a machine that *has* the network.
`--machine` names the manifest to build for and `--arch` its CPU. Neither has a
default: this runs on a machine that is deliberately not the one being built for,
so a default silently targets whichever box was convenient when it was written.
Both offer a numbered list on a terminal, and a scripted caller that omits one
gets a usage error rather than a prompt.

The OS is not asked for. The manifest declares it, and the CPU is the only thing
a manifest never states — which is why building for Apple Silicon differs from
building for an Intel Mac by `--arch` alone.

It also carries what the bootstrap itself needs before any of that can run: the
`uv` binary for the target platform, and a wheelhouse holding the CLI's whole
dependency closure. Without those the restricted machine can unpack a bundle it
has no way to install from, which is the one failure the bundle exists to
prevent. The wheels cover every CPython at or above this package's
`requires-python`, because which interpreter the target has is a fact only the
target knows.

The tarball is named after the date, the manifest and the target platform, so
handing it to something else means retyping a name that changes every build.
`--print-path` writes the finished path to stdout, which makes the handoff a
substitution rather than a copy-paste:

```bash
ifiles upload "$(dotfiles bundle create --machine wsl-work-workstation --arch x86_64 --print-path)"
```

The build log is unaffected — it goes to stderr either way, so it still reaches
the terminal — and the path is printed only after the cache prune finishes, so
nothing downstream sees a bundle that is still being written.

The builder is `src/dotfiles/create_bundle.py`. It was shell until the naming
above proved the problem — a bash function has no return value, so "produce a
tarball and tell the caller its name" has no direct expression there. Its logic
— checksum parsing, cache keys, wheel tag matching, archive repackaging — is
covered by `tests/install/test_create_bundle.py`, which needs neither a network
nor a container and runs in well under a second.

Move the tarball across, then `./install.sh --machine NAME --offline` finds it in
`./` or `~/`, extracts it to `~/installers/`, installs uv and the CLI from the
bundle with no index at all, and prints the `dotfiles apply --machine NAME
--offline` that installs the machine from it. The flag is needed on both, and for
different reasons: it says where the bootstrap gets uv and the wheels, and it
says the apply installs from `~/installers/` rather than from the network.

On a machine that already has the CLI, the bootstrap is not the way to unpack a
newer bundle — `dotfiles bundle stage` does that alone, and the apply does it
unasked when it finds nothing staged.

This path is tested end to end by `uv run pytest tests/e2e --docker -k offline`:
it builds a bundle, starts a container blackholed to exactly the hosts this page's
results file reports blocked, and asserts the install completes from cache. If you
change the bundle format, that is what catches it.

The container's network is derived from `connectivity-results.txt` rather than
typed into the test, and it asserts both halves — that the blocked hosts really
are unreachable, and that the reachable ones really are. Only the first was ever
checked, and the test drifted stricter than the firewall: it blackholed
`github.com` outright, so theme, font and bashselfupdate failed to clone in a test
of a network where they clone fine, and the log read as though the bundle had a
gap it does not have.

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

A separate Windows bundler existed while the Windows side was reached from WSL.
It went with that bridge, and the capability moved into `create_bundle.py` rather
than going with it, which is where it belongs now that Windows is an ordinary
machine rather than something addressed across `/mnt/c`.

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
