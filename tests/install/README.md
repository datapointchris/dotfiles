# Installation Tests

Tests for dotfiles installation and deployment infrastructure.

The pytest modules directly under this directory are the Python side — the
release resolver, the bundle builder, the run records, the failure report. The
install scripts that are still shell are driven from `tests/shell/`.

`eza -1 tests/install/` lists what is here.

## Tiers

`e2e/` holds the two runs that cannot be a container: a real macOS user account
and the current machine. Every container install is `tests/e2e/`, driven by
pytest as one rig with the environments as parameters.

```bash
task test                                                 # everything, no Docker
task test:e2e                                             # every environment
uv run pytest tests/e2e --docker --environment archlinux  # one of them
```

`--keep` leaves the containers up afterwards and `--reuse` keeps a kept
container's OS state while still refreshing the repo inside it.

`docker/` holds the image definitions those runs build from, and
`verification/` the two scripts an e2e run finishes with — what the manifest
declared is present and in the expected prefix, and nothing is installed twice by
two different methods.
