# A Test Writes Through a Deployed Symlink

## Problem

Every tool that resolves the repo registry stopped working at once. `repos-registry`
exited 1:

```text
nothing names a registry: set repos_registry in /home/chris/.config/dotfiles/config.toml
```

Two things had happened. The tracked source
`configs/trust/fleet/.config/dotfiles/config.toml` was cut from 57 lines to 2,
uncommitted on `main`, and the deployed `~/.config/dotfiles/config.toml` had stopped
being a symlink and was a regular 27-byte file. Every other deployed config was still
a link into the repo, and the run records name the only two applies in the window, so
a bad deploy was ruled out early.

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

That real path was a symlink, and two different writes through it produce two
different damages. Both were reproduced in a scratch directory against a five-line
source:

```text
write through a LIVE link          write that unlinks first
open(path, 'w')                    Path.unlink(); write_text(...)

source: 5 lines -> 2               source: 5 lines, untouched
        same inode                 deployed path: 27-byte regular file
deployed path: still a link        the link is gone
```

The first is why the tracked source lost 55 lines. The second is why the deployed
path stopped being a link, because `Path.unlink()` on a symlink removes the link
rather than its target. One suite run did both, and it also filled
`$XDG_STATE_HOME/dotfiles/` with fixture run records — enough that
`dotfiles report latest` read a fixture belonging to another machine.

**No test runner is required for this.** `atuin init zsh` reached through a symlink
whose source has been deleted creates a 16k default config **at the repo path**, and
`configs/common/.config/zsh/.zshrc` runs it at shell startup. So deleting a declared
config source while its link is still deployed hands the consuming tool a writable
path into the checkout.

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

When deleting a declared config source, replace its deployed link with a real file
*before* the source goes, not after. Copy through the link, remove the link, move the
copy into place. Doing it in the other order leaves a window in which the consuming
tool recreates the source it was meant to lose.

## Key Learnings

- **A deployed symlink makes any write to the target a write into the repo.** The
  checkout is machine state in both directions, and the second direction is the one
  nothing warns about. It is ordinary `open(path, 'w')` behavior rather than anything
  unusual about the writer, so a test, a tool and an editor all do it.
- **A live link and a dangling one damage different ends.** Through a live link the
  write truncates the tracked source in place. Through a dangling one it creates the
  source. Which one you are looking at decides which repair you need.
- **Mutating a path helper mutates every caller of it.** Grep the helper before
  breaking it. A variable that looks like it serves the state directory served the
  config file and a systemd unit as well.
- **Restoring the source is not restoring the machine.** A session that ran only
  `git restore` would have reported a repaired machine over a still-severed link.
- **The detector exists and has no automatic remedy.** `FOREIGN` becomes a `STALE`
  verdict with `Repair.BY_HAND`, so the scheduled check reports it and `apply` cannot
  clear it. Detection hands the work to a person and the clock keeps running.
- **A guard that fires on a narrow shape stays green for the wide one.**
  `no_run_artifacts_on_this_machine` fails on records that are empty *and* carry this
  machine's id. The leaked records were neither, so it passed throughout.
