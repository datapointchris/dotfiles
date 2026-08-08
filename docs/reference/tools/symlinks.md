# Symlinks Manager

Deploys this repo into `$HOME` as symlinks, in layers: a common base and one
overlay per coordinate axis on top of it.

`dotfiles symlinks --help` lists the verbs. There is one deployment verb —
`apply` — because reconciling means the machine ends up matching the
declaration, and a create-only pass leaves a broken link behind whenever a
source is deleted. The old `link`/`relink` split asked the caller to know which
kind of change they had just made, and got the answer wrong in exactly the case
that mattered.

`check` and `apply` decide **per link**: what the repo declares, against what is
at each target. That is why `check` can report a declared link that was never
deployed — the pass this replaced recreated all of them every run and could only
say whether any were *broken*, so a file added to `configs/` and never deployed
read as converged. It is also why nothing is unlinked before being rewritten: a
deployed link produces no change at all, which closes the window a daemon
watching its own config used to regenerate a default inside.

## Architecture

Each of the three trees — `configs/`, `shell/`, `apps/` — is `common/` plus
`<axis>/<value>/` directories, one per coordinate axis the machine sits on.
`common` links first and the overlays follow in axis order.

Which directory names are legal is `OVERLAY_DIRS` in `src/dotfiles/coordinates.py`,
and a machine's own list is the `DOTFILES_*` block of `~/.env`. Nearly all of
them are absent on disk: an axis earns a directory only where something actually
differs along it, and implying one per axis value is the overlay explosion this
scheme exists to avoid.

Overlays flatten onto the destination in `configs/` and `apps/`, because a config
has to land where the program reading it looks. `shell/` keeps the
`<axis>/<value>` path, because the only thing that reads `~/.local/shell` is
`.zshrc`, which walks those directories by name.

Two overlays are never allowed to claim one target. Deployment is ordered, so a
conflict would not fail — it would deploy whichever layer comes later and report
success — which is why `tests/symlinks/test_overlays.py` asserts it against every
machine the axes can express rather than the four that exist.

## Targets this manager did not create

A link pass replaces a target only when it owns it — a symlink pointing into the
repo, including a broken one left by a deleted source. Anything else (a real
file, or a symlink pointing somewhere else) is **refused, listed, and left
untouched**, and the run exits non-zero.

This is not politeness about a user's files. The write is an unlink followed by a
symlink, so it removes whatever is at the path, and `uv tool dir --bin` is
`~/.local/bin` — the same directory the apps layer links into. Without the check,
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

Most of `configs/` mirrors into `$HOME` directly. Two trees do not, and are
declared as their own layers with a different destination:

**`apps/`** → `~/.local/bin/`. An app whose job is to change the calling shell
adds a function in `shell/common/functions.sh` instead; a symlinked command
cannot export into the shell that ran it.

**`shell/`** → `~/.local/shell/`. Shell *code* — functions and aliases — rather
than config, which is why it does not sit under `~/.config`. Only the resolved
platform's overlay file is linked.

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

## Broken links

`check` finds them and touches only links resolving into this repo. Do not sweep
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

There was a second `symlinks` console script until 2026-08-08, taking a layer per
invocation. It went with the pass it drove: it was a front door with different
semantics from the one everything actually called, including a `check` whose
`--auto-fix` defaulted to true — a read verb that deleted files.

## See Also

- [Learnings: Symlinks Path Gotchas](../../learnings/symlinks-path-gotchas.md)
