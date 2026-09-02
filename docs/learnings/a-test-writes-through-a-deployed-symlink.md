# A Test Writes Through a Deployed Symlink

## Problem

Every tool that resolves the repo registry stopped working at once. `repos-registry`
exited 1:

```text
nothing names a registry: set repos_registry in /home/chris/.config/dotfiles/config.toml
```

Two things had happened and only the first was visible. The tracked source
`configs/trust/fleet/.config/dotfiles/config.toml` was cut from 57 lines to 2 as an
uncommitted modification on `main`. Separately, the deployed
`~/.config/dotfiles/config.toml` had stopped being a symlink and was a regular
27-byte file, while every other deployed config was still a link into the repo.

Nothing was edited by hand, and the run records name the only two applies in the
window, so a deploy against a half-written tree was ruled out early.

The cause was a mutation taken to prove a test could go red. One line in
`src/dotfiles/paths.py` was changed so `xdg_home` ignored its variable:

```python
declared = None    # was os.environ.get(variable)
```

then the whole suite was run through it.

`xdg_home` serves four call sites, not one:

```text
paths.py:75              XDG_STATE_HOME   -> state directory
paths.py:104             XDG_CACHE_HOME   -> cache directory
settings.py:51           XDG_CONFIG_HOME  -> dotfiles/config.toml
providers/ghrelease.py:422  XDG_CONFIG_HOME  -> systemd/user
```

Killing the variable killed all four. Every test that redirects `$XDG_CONFIG_HOME`
and then writes a config resolved to the real path instead of its sandbox.

That real path was a symlink, so `write_text` followed it into the checkout and
truncated the tracked source. A later test doing unlink-then-create severed the link
and left a regular file, because `Path.unlink()` on a symlink removes the link rather
than its target. One run produced both ends, and it also filled
`$XDG_STATE_HOME/dotfiles/` with fixture run records — enough that
`dotfiles report latest` read a fixture belonging to another machine.

## Solution

Two repairs, because there are two ends and one is not enough:

```bash
git restore -- configs/trust/fleet/.config/dotfiles/config.toml
dotfiles symlinks apply --force
```

`git restore` fixes the source. Only the forced apply reattaches the deployed end —
`symlinks plan` reports the stray file as `stale` and refuses to touch it, because
`core.link_ownership` answers `FOREIGN` for a regular file at a declared target and
the resource returns `REFUSED` without `--force`. That refusal is the design working:
it will not overwrite a file it did not create.

Run a mutation with `HOME` and every XDG variable pointed at a scratch directory, and
say in the receipt that it was sandboxed.

## Key Learnings

- **A deployed symlink makes any write to the target a write into the repo.** The
  checkout is machine state in both directions, and the second direction is the one
  nothing warns about.
- **Mutating a path helper mutates every caller of it.** Grep the helper before
  breaking it. A variable that looks like it serves the state directory served the
  config file and a systemd unit as well.
- **Restoring the source is not restoring the machine.** A session that ran only
  `git restore` would have reported a repaired machine over a still-severed link.
- **The detector exists and has no automatic remedy.** `FOREIGN` becomes a `STALE`
  verdict with `Repair.BY_HAND`, so the scheduled check reports it and `apply` cannot
  clear it. Detection hands the work to a person and the clock keeps running.
- **A guard that fires on a narrow shape stays green for the wide one.**
  `no_run_artefacts_on_this_machine` fails on records that are empty *and* carry this
  machine's id. The leaked records were neither, so it passed throughout.
