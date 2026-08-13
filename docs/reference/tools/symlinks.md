# Symlinks Manager

Deploys this repo into `$HOME` as symlinks: a common base, plus one
`<axis>/<value>` directory per coordinate axis the machine sits on.

`dotfiles symlinks --help` lists the verbs. There is one deployment verb —
`apply` — because reconciling means the machine ends up matching the
declaration, and a create-only pass leaves a broken link behind whenever a
source is deleted. The old `link`/`relink` split asked the caller to know which
kind of change they had just made, and got the answer wrong in exactly the case
that mattered.

`plan` and `apply` decide **per link**: what the repo declares, against what is
at each target. That is why `plan` can report a declared link that was never
deployed — the pass this replaced recreated all of them every run and could only
say whether any were *broken*, so a file added to `configs/` and never deployed
read as converged. It is also why nothing is unlinked before being rewritten: a
deployed link produces no change at all, which closes the window a daemon
watching its own config used to regenerate a default inside.

## Architecture

Each of the three trees — `configs/`, `shell/`, `apps/` — is `common/` plus
`<axis>/<value>/` directories, one per coordinate axis the machine sits on.
`common` links first and the coordinate directories follow in axis order.

Which directory names are legal is `AXIS_DIRS` in `src/dotfiles/coordinates.py`,
and a machine's own list is the `DOTFILES_*` block of `~/.env`. Nearly all of
them are absent on disk: an axis earns a directory only where something actually
differs along it, and implying one per axis value is the directory explosion this
scheme exists to avoid.

The two trees mean opposite things by their directories. `configs/` and `apps/`
hold **variants**: they flatten onto the destination, so exactly one file arrives
and the rest are versions this machine did not select. `shell/` holds **layers**:
it keeps the `<axis>/<value>` path and every directory that exists is sourced
together, because the only thing that reads `~/.local/shell` is `.zshrc`, which
walks those directories by name.

Two variants are never allowed to claim one target. Deployment is ordered, so a
conflict would not fail — it would deploy whichever directory comes later and report
success — which is why `tests/symlinks/test_coordinate_directories.py` asserts it
against every machine the axes can express rather than the four that exist.

## Targets this manager did not create

A link pass replaces a target only when it owns it — a symlink pointing into the
repo, including a broken one left by a deleted source. Anything else (a real
file, or a symlink pointing somewhere else) is **refused, listed, and left
untouched**, and the run exits non-zero.

This is not politeness about a user's files. The write is an unlink followed by a
symlink, so it removes whatever is at the path, and `uv tool dir --bin` is
`~/.local/bin` — the same directory the apps tree links into. Without the check,
installing this project as a uv tool and then running a link pass means the
second silently deletes the executable that the first installed.

`--force` adopts refused targets, which is what a machine that already had
dotfiles of its own needs on first install.

**A name `[project.scripts]` declares is skipped outright, `--force` or not.**
The two are competing for one path and the declaration wins; there is no state of
the machine in which linking an `apps/` file over the console script is right.
The names are read from `pyproject.toml` rather than from the installed
distribution, because during a bootstrap nothing is installed yet and the answer
has to be the same either way.

## Directories that do not map to `$HOME`

Most of `configs/` mirrors into `$HOME` directly. Two trees do not, and name a
different destination:

**`apps/`** → `~/.local/bin/`. An app whose job is to change the calling shell
adds a function in `shell/common/functions.sh` instead; a symlinked command
cannot export into the shell that ran it.

**`shell/`** → `~/.local/shell/`. Shell *code* — functions and aliases — rather
than config, which is why it does not sit under `~/.config`. Only the layers
this machine's coordinates select are linked, and each keeps its `<axis>/<value>`
path so a sourced file says which coordinate asked for it.

`~/.local/shell/local.sh` is the exception to all of it: a real file, not a
symlink, holding machine-local shell code that exists in no repo. Nothing
declares it, and only a link resolving into the source tree is ever unlinked, so
a deploy leaves it alone.

Go apps, and personal CLI tools like `theme` and `font`, are not symlinked at
all — they have their own installers. See
[App Installation Patterns](../../learnings/app-installation-patterns.md).

## Exclusions

`EXCLUDE_PATTERNS` in `src/dotfiles/symlinks/core.py` is the list. Three of its
rules exist because of bugs that are easy to reintroduce:

- Match `/.git/` or a `.git/` prefix, never the substring — `.git/` as a
  substring excluded `.gitconfig`.
- Take relative paths from `Path.relative_to(walk_up=True)`, never by hand.
  Manual calculation broke 122 symlinks.
- `.gitconfig`, `.gitignore` and `.gitattributes` are needed on every platform
  and must never be excluded.

All three are worked through in
[Learnings: Symlinks Path Gotchas](../../learnings/symlinks-path-gotchas.md).

### Where the orphan scan will not go

`EXCLUDE_SEARCH_DIRS` is a second, separate list: it governs where the walk that
finds broken links descends, not what gets linked. Entries match whole path
components as a contiguous run, so `.config/environment.d` is not read as `env`
and `.local/share/buildkit` is not read as `build` — both are directories this
repo can legitimately deploy into.

It names the expensive subtrees of `~/Library` rather than `~/Library` itself,
because `configs/os/darwin/Library/Application Support/` is deployed and an
exclusion on the parent takes the deployed tree with it. `Messages/Attachments`
and `Mail` are named individually for the cost: the walk runs inside every plan,
apply and check, and neither is reachable as a deployment target.

### The depth ceiling is a live constraint on the darwin variant

`SEARCH_DEPTH` bounds that walk at five components below `$HOME`, and the
deepest path this repo deploys sits exactly on it —
`Library/Application Support/Vivaldi/External Extensions/<extension>.json`.
Adding a directory level under `External Extensions/`, or lowering the ceiling,
drops that link out of the scan with nothing said: it stays deployed, and no run
ever reports it stale. `tests/symlinks/test_core.py` builds that exact path at
that exact depth, so neither change can happen quietly.

## Broken links

`plan` finds them — an orphan is drift `apply` repairs by pruning — and it
touches only links resolving into this repo. Do not sweep
them by hand with a `find -delete` across `$HOME` — that deletes every broken
link on the machine, including ones this manager never created and is not
responsible for.

"Module not found" in Neovim after adding files under
`configs/common/.config/nvim/lua/` is almost always a missing symlink rather than
a plugin problem.

## Development

`src/dotfiles/resources/symlinks.py` decides — what the repo declares, what is at
each target, and what to do about the difference. `src/dotfiles/symlinks/core.py`
holds the primitives it decides with: the exclusion rules, relative-path
calculation, ownership, and the `/etc/skel` comparison. `src/dotfiles/deploy.py`
is the epilogue that runs after a deploy.

Tests for the decisions are in `tests/resources/test_symlinks.py`, which builds a
whole synthetic repo and home per test; the primitives are covered in
`tests/symlinks/`. Both run on every commit.

They sat in `symlinks/tests/` until 2026-08-08 and were collected by nothing —
`testpaths` names `tests` only, so the whole file ran for no one. A test
directory outside the collected root is worse than no tests, because the count
reads as coverage.

There was a second `symlinks` console script until 2026-08-08, taking one
coordinate directory per invocation. It went with the pass it drove: it was a front door with different
semantics from the one everything actually called, including a `check` whose
`--auto-fix` defaulted to true — a read verb that deleted files.

## See Also

- [Learnings: Symlinks Path Gotchas](../../learnings/symlinks-path-gotchas.md)
