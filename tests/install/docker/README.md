# Docker-Based Installer Testing

Run one installer script in an isolated container, with real network calls and a
real installation. For the whole-machine equivalent — a full `install.sh` per
environment, including the offline lifecycle — see `tests/e2e/`.

## What is here

`ls` this directory rather than trusting a list; each script's `--help` says what
it takes. The shape is a three-tier image strategy, and that is the part worth
explaining:

1. Base OS (`ubuntu:26.04`, matching the work WSL)
2. A reusable image with system packages already installed
3. Ephemeral per-test containers built from it

Tier 2 is why a test takes seconds rather than minutes: the expensive half —
`apt` — happens once, and every test reuses it. `build-base.sh --ubuntu 24.04`
builds and tags an older one separately.

## Running one

```bash
./build-base.sh                                              # one-time, minutes
./run-installer-test.sh install/common/custom-installers/bats.sh --validate bats
./run-installer-test.sh install/wsl/system-packages.sh       # should skip: already installed
```

`--keep` leaves the container for `docker exec -it <name> /bin/bash`, and
`--no-cache` on `build-base.sh` forces a rebuild.

## What this no longer covers

The `github_releases` installers were 23 bash scripts and are now
`src/dotfiles/providers/`, so there is nothing here to point at one. Their
coverage is `tests/install/test_ghrelease.py` for the install sequence,
`tests/install/test_release_urls.py --e2e` for what upstream actually publishes,
and `tests/e2e/` for a real install in a real container.

What remains testable here is a script: the custom installers, and the
per-platform system-package scripts.

## Troubleshooting

**Base image not found** — `./build-base.sh`.

**Permission errors** — the runner fixes ownership after copying files; check the
`chown` step completed.
