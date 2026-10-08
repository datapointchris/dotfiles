# uv tool install Ignores the Lock

## Problem

A git tool installed by dotfiles ran on dependency versions its own CI never tested.
`uv tool install '<name> @ git+<repo>@<tag>'` reads the tag's `pyproject.toml` and
resolves every dependency afresh. It never reads the tag's `uv.lock`, and CI tests the
lock. Every installed git tool on a workstation differed from its tag's lock. logsift
v0.1.4 locks typer 0.20.0 and ran 0.27.2. From typer 0.27, `typer.Exit` is typer's own
class rather than click's. A tool catching click's class saw every clean finish as a
crash and exited 3, while its CI passed.

dotfiles' own CLI had the same gap. `install.sh` and `dotfiles update` both run
`uv tool install --editable`, which ignores the lock too.

## Solution

`uv export` turns the lock into requirements, and they reach `uv tool install` in two
files: registry pins as `--constraints`, URL pins as `--overrides`.
`src/dotfiles/uv_lock.py` holds the mechanism. The git tool provider clones the tag at
depth 1 to export its lock. A tag with no `uv.lock` installs unconstrained, with a
warning naming the tag.

`packages check` reports a tool at its newest tag as drift when the tag carries a lock
and the tool's receipt holds neither list. The release cache records whether each tag
carries one, read once per release with a `HEAD` on the contents endpoint.

## Key Learnings

- **A git pin sent as a constraint is refused.** The package declares the bare URL and
  the lock records it at a commit, so uv fails with
  ``Requirements contain conflicting URLs for package `toon-format` ``. As an override
  it installs the locked commit.
- **An override drops the extras the tool asked for.** The export names a git package
  bare, and an override replaces the declared `gitdep[x] @ git+...` whole, so `x`'s
  dependencies never install. Only the lock's edges carry `extra = ["x"]`, so the
  override line is rebuilt from a walk of them.
- **uv does not check the hashes in a constraints file.** An install with every hash
  zeroed succeeded under `--no-cache`, so the export drops them rather than imply a
  verification nothing performs.
- **The receipt keeps both lists, and only `uv tool upgrade` honors them.**
  `uv tool install --force <requirement>` with no flags resolves afresh and writes a
  receipt without them. A tool's own self-updater that runs it undoes a locked install.
- **An empty requirements file warns on every install**:
  `warning: Requirements file ... does not contain any dependencies`. Name a file only
  when it has lines.
- **A tool with no dependencies records no lists.** Its lock pins nothing, so its receipt
  holds no constraints. The check reads the environment as well, and one holding only
  the tool had nothing to hold.
