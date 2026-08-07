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

The tarball is named after the date, the manifest and the target platform, so
handing it to something else means retyping a name that changes every build.
`--print-path` writes the finished path to stdout, which makes the handoff a
substitution rather than a copy-paste:

```bash
ifiles put "$(./install.sh --create-offline-bundle --print-path)"
```

The build log is unaffected — it goes to stderr either way, so it still reaches
the terminal — and the path is printed only after the cache prune finishes, so
nothing downstream sees a bundle that is still being written.

The builder is `install/offline/create_bundle.py`, run under the system
`python3` for the same reason `parse_packages.py` is: that is the interpreter
guaranteed to have PyYAML, and the builder imports `parse_packages` directly
rather than shelling out to it. It was shell until the naming above proved the
problem — a bash function has no return value, so "produce a tarball and tell
the caller its name" has no direct expression there. Its logic — checksum
parsing, cache keys, archive repackaging — is now covered by
`tests/install/test_create_bundle.py`, which needs neither a network nor a
container and runs in well under a second.

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

`install/wsl/windows_bundle.py` builds it, sharing `install/github_release.py`
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
