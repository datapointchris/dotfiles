# The container image the e2e tier installs into

One image, built once, with the expensive half of a machine already on it. For
what runs *in* it — a full `dotfiles apply` per environment, including the offline
lifecycle — see `tests/e2e/`.

## What is here

`ls` this directory rather than trusting a list; each script's `--help` says what
it takes. The shape is a two-tier image strategy, and that is the part worth
explaining:

1. Base OS (`ubuntu:26.04`, matching the work WSL)
2. A reusable image with system packages already installed

Tier 2 is why a run takes seconds to start rather than minutes: the expensive
half — `apt` — happens once, and every container reuses it.
`build-base.sh --ubuntu 24.04` builds and tags an older one separately.

```bash
./build-base.sh                    # one-time, minutes
uv run pytest tests/e2e -m docker  # what uses it
```

`--no-cache` forces a rebuild.

## Why there is no per-installer runner any more

There are no installer scripts. `run-installer-test.sh` took one script path, ran
it in a container and validated a binary came out, and it went with the last
script it could be pointed at — TPM's, in the commit that made the two plugin
managers providers. The 32 release and custom installers had gone the same way
before it, and the platform package scripts before them.

What replaced its coverage is per-mechanism: `tests/install/` for the install
sequences a provider drives, `tests/install/test_release_urls.py --e2e` for what
upstream actually publishes, and `tests/e2e/` for a real install in a real
container — which is the one thing this image is still for.

## Troubleshooting

**Base image not found** — `./build-base.sh`.

**Permission errors** — the build fixes ownership after copying files; check the
`chown` step completed.
