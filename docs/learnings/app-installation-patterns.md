# App Installation Patterns

**Context**: Managing custom CLI apps with different installation methods.

## App Categories

### 1. Go Apps (Remote Install via `go install`)

**Examples**: `todoui`, `forge`

**Installation**: declared in `install/packages.yml` under `go_tools` and installed with
`go install` by `src/dotfiles/providers/gotool.py`.

**Development**: Source code lives in `~/tools/{app}/`. Changes are tested locally with
`go run .` or `go build`, then pushed to GitHub. Fresh installs get the latest from
GitHub.

**Binary location**: `~/go/bin/`

### 2. Shell Script Apps (Symlink Pattern)

**Examples**: `notes`, `packup`, `aws-profiles`

A Python app here that outgrows a single file graduates to category 5, subject to
the dependency constraint stated there.

**Location**: `apps/common/`, plus `apps/<axis>/<value>/` for one that only makes
sense at a coordinate — the rofi menus are under `apps/display/wayland/`.

**Installation**: every variant the machine's coordinates select is symlinked into
`~/.local/bin/` by `dotfiles symlinks apply`. Directories are skipped, so only
executable files are linked, and the variants flatten onto one destination because
a command has to be on `PATH` rather than under a directory naming why it exists.

**An app that has to change the calling shell is two pieces: a command and a function.** A
subprocess cannot export a variable into the shell that ran it. So the command does the
work and prints a decision, and a shell function reads that decision and does the
exporting. The function belongs in `shell/common/functions.sh`, not in `apps/`.
`aws-profiles` is the in-repo example, and the comment above its definition there carries
the reasoning and the alternative it rejected.

The underscore on `_aws-profiles` marks the half that is not the way in. It is safe in
`~/.local/bin` — the `_name` convention that would collide is zsh's completion functions,
which live in `fpath`, not `PATH`.

### 3. Personal CLI Tools (Git Clone Pattern)

**Examples**: `theme`, `font`

**Installation**: `src/dotfiles/providers/custom.py` runs the vendor's own install script,
which clones from GitHub to `~/.local/share/` and symlinks its bin into `~/.local/bin/`.
Once the checkout exists, converging means delegating to the tool's own `update` rather
than re-running the installer over a live checkout.

**Development**: Source code in `~/tools/{app}/`. Changes tested locally, pushed to
GitHub. Run `theme update` or `font update` to pull updates to the installed version.

### 4. Python Tools (Remote Install via `uv tool install`)

**Examples**: `relate`, `logsift`, `indy`, `refcheck`, `syncer`, `safekeep`

**Installation**: declared in `install/packages.yml` under `git_uv_tools` and installed
with `uv tool install`, pinned to the repo's newest release tag. Why the pin is not
optional, and what `tracks_branch` declares, are the module docstring in
`src/dotfiles/providers/uvtool.py`.

**Development**: Source code lives in `~/tools/{app}/`. Changes are tested locally, then
pushed to GitHub — and a release must be cut for the fleet to pick them up, since the
install tracks release tags rather than `main`.

**Binary location**: `~/.local/bin/` (managed by uv)

### 5. This Package's Own Commands (`[project.scripts]`)

**Examples**: `dotfiles`, `packages`, `worktree`, `tmux-place`, `tmux-rearrange`

**Location**: a module or subpackage under `src/dotfiles/`, with an entry in
`[project.scripts]` naming the callable. `pyproject.toml` is the list.

**Installation**: the entry point is written into the tool venv's bin directory by
`uv tool install`, which is what `install.sh` runs and what `dotfiles update`
re-runs whenever `pyproject.toml` or `uv.lock` changes. An editable install points
at the working tree, so a code change needs nothing — but a *new* command does not
exist on the machine until that reinstall, because entry points are settled once at
install time.

`dotfiles symlinks apply` skips any name `[project.scripts]` claims, so a file in
`apps/` and a console script cannot both take one path in `~/.local/bin`. The
declaration wins.

**Where category 2 graduates to.** A Python app in `apps/` that outgrows a single
file belongs here — but only if its dependencies can be installed from a wheelhouse
with no network. The offline bootstrap is
`uv tool install --offline --no-index --find-links "$BUNDLE/wheels"`, and that
resolves `[project.dependencies]` in full. Two things follow:

- A dependency published on PyPI is fine. `create_bundle.py` reads the pinned
  closure out of `uv export` and fetches each wheel by name and version.
- A dependency declared through `[tool.uv.sources]` as a git ref is not. `uv export`
  emits it as `name @ git+https://...` with no `==`, so the bundle omits it — and
  even with the correct wheel staged, uv routes a git source to git and
  `--find-links` does not override it, so the offline install of *the whole CLI*
  fails. Such an app stays in `apps/`, where its PEP 723 header resolves its own
  environment. `prs` is that case.

**Binary location**: `~/.local/bin/`, via `uv tool dir --bin`

## Related Files

- `install/packages.yml` — where categories 1 and 4 are declared
- `pyproject.toml` — where category 5 is declared, under `[project.scripts]`
- `src/dotfiles/resources/symlinks.py` — symlink deployment; its `TREES` is what sends `apps/` to `~/.local/bin/`
- `src/dotfiles/providers/custom.py` — personal tool installers
