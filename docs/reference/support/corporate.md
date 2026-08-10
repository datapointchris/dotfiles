# Restricted Networks

The work machine sits behind a firewall that blocks most of what an install
reaches for. Three pieces of machinery exist for it, and none of them are the
generic advice about proxies and registry mirrors — that was the previous
content of this page, and it described an installer this repo does not use.

## Find out what is actually blocked

`bash install/offline/test-connectivity.sh` walks every URL the install touches
and writes a pass/fail line per host to
`install/offline/connectivity-results.txt`. Run it on the restricted machine
first: the answer is rarely "the internet is blocked" and usually "GitHub
release assets are blocked but the API is not", which changes what you need to
carry in.

The results file is committed deliberately. It is a record of one network's
behaviour at one time, which is the only way to compare against it after the
firewall rules change.

## Install without the network

`dotfiles bundle create` downloads every GitHub release binary, cargo binary and
install script into a single tarball, on a machine that *has* the network.
`--platform` targets the machine you are building for, not the one you are on —
the default is `linux-x86_64`, so building on a Mac for WSL needs no flag, and
building for Apple Silicon does.

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
ifiles put "$(dotfiles bundle create --print-path)"
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

`task windows:bundle` and `task windows:offline` are the same idea for the Git
Bash side. See [Task Reference](../tools/tasks.md).

`src/dotfiles/windows_bundle.py` builds it, sharing `src/dotfiles/github_release.py`
with the Linux bundler — so a Windows asset is now verified against the checksum
its release published, wherever one exists. The shell version it replaced
verified nothing at all, which mattered most on exactly the network this page is
about. Several of these projects publish no Windows checksum (fd, delta, bat,
zoxide, eza at the time of writing); the build says so per tool rather than
staying quiet, so what is and is not verified is visible while it is being
built.

## Why the Neovim setup does not need any of this

Neovim uses native LSP rather than Mason, so opening an editor does not reach
`raw.githubusercontent.com` at all. Language servers arrive through
`npm_globals` and `uv_tools` in `install/packages.yml` like every other tool,
which means the bundle above already carries them. There is nothing
Neovim-specific to arrange.
