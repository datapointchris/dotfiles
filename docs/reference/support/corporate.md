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

`./install.sh --create-offline-bundle` downloads every GitHub release binary,
cargo binary and install script into a single tarball, on a machine that *has*
the network. `--platform` targets the machine you are building for, not the one
you are on — the default is `linux-x86_64`, so building on a Mac for WSL needs
no flag, and building for Apple Silicon does.

Move the tarball across, then `./install.sh --offline` extracts it to
`~/installers/` and installs from there. `install.sh --help` prints the full
sequence including the `python3 -m http.server` route for when scp is also
blocked.

This path is tested end to end: `tests/install/e2e/offline-docker.sh` builds a
bundle, blocks GitHub inside a container, and asserts the install completes from
cache. If you change the bundle format, that test is what catches it.

## Windows tools when winget is blocked

`task windows:bundle` and `task windows:offline` are the same idea for the Git
Bash side. See [Task Reference](../tools/tasks.md).

## Why the Neovim setup does not need any of this

Neovim uses native LSP rather than Mason, so opening an editor does not reach
`raw.githubusercontent.com` at all. Language servers arrive through
`npm_globals` and `uv_tools` in `install/packages.yml` like every other tool,
which means the bundle above already carries them. There is nothing
Neovim-specific to arrange.
