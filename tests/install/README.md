# Installation Tests

Tests for dotfiles installation and deployment infrastructure.

The pytest modules directly under this directory are the Python ones — the
release resolver, the bundle builder, the run records. The `unit/` and
`integration/` subdirectories are what remains of the bats suites, and both are
emptying: each file leaves as its coverage lands in pytest, and the bats runner
and its CI job go with the last one. Nothing new belongs there.

`eza -1 tests/install/` lists what is here; `bats -c tests/install/unit/*.bats`
counts what is left to port.

## Tiers

`e2e/` holds the two runs that cannot be a container — a real macOS user account
and the current machine. Every container install is `tests/e2e/`, driven by
pytest as one rig with the environments as parameters:

```bash
uv run pytest tests/e2e --docker                          # every environment
uv run pytest tests/e2e --docker --environment archlinux  # one of them
```

`--keep` leaves the containers up afterwards and `--reuse` keeps a kept
container's OS state while still refreshing the repo inside it.

`integration/` is the tier that reaches for Docker images and live release APIs,
which is why no CI job runs it. `unit/` needs nothing but a checkout.

```bash
task test:unit          # the runner-safe bats tiers
uv run pytest tests/    # everything Python, no Docker
```
