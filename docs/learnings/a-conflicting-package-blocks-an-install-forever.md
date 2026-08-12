# A Conflicting Package Blocks an Install Forever

## Problem

`dotfiles apply` rebuilt sioyek from source for four minutes and then failed, every
run, with nothing actionable:

```text
✗ system/sioyek: yay -S exited 1
```

The reason was only in the run transcript, not on the row:

```text
:: sioyek-git-2.0.0.r1150.gcd319eb4-1 and sioyek-2.0.0-7 are in conflict. Remove sioyek? [y/N] error: unresolvable package conflicts detected
error: failed to prepare transaction (conflicting dependencies)
```

`packages.yml` had moved the entry from `aur: sioyek` to `aur: sioyek-git` when
upstream deleted the first package, and the machine still carried what the old
name built. `sioyek-git` declares `Conflicts With: sioyek`, so pacman had to
remove one to install the other. Every installer in `providers/syspkg.py` runs
`--noconfirm`, pacman's conflict prompt is a `noyes` — default **no** — and
`--noconfirm` takes the default. The transaction could therefore never succeed.

The three verbs each reported something different, and each was right about what
it measured:

```text
check   converged, because a missing package is drift rather than a fault
plan    missing, which promises an apply will install it
apply   built, failed, exited 1
```

Nothing measured the fact that actually decided the outcome — that a package
standing in the way was installed.

## Solution

`system_packages` entries take `supersedes`, naming what the entry took over from:

```yaml
  - name: sioyek
    aur: sioyek-git
    supersedes: [sioyek]
```

`evidence.blocker` reads it against the inventory already loaded for the install
check. A superseded name still present produces a `Blocker`, `repair_for` turns
that into `Repair.BY_HAND`, and the existing fold does the rest: check reports it
with the removal command, plan stops promising an install, and apply renders the
finding without attempting the build.

Declared rather than detected on purpose. A package manager can be asked what a
candidate conflicts with, but for the AUR that is a remote RPC call, and `check`
runs at a prompt, in a pre-commit hook, on a timer and under `--offline`.

## Key Learnings

- A verdict of `missing` is a promise that `apply` will fix it. An item apply
  cannot fix needs a different answer, or every verb downstream inherits the lie.
- `Repair.BY_HAND` already meant "real, and not ours to repair". Reaching for the
  existing vocabulary beat adding a `Verdict`, which every renderer would have had
  to learn.
- `--noconfirm` is not "answer yes". It is "take the default", and for a conflict
  removal the default is no.
- The cost of a wrong answer here was four minutes of compile per run. An install
  that cannot succeed should be refused before it is attempted, not after.
