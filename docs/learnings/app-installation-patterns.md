# App Installation Patterns

**Context**: Managing custom CLI apps with different installation methods.

## Four App Categories

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

## Related Files

- `install/packages.yml` — where categories 1 and 4 are declared
- `src/dotfiles/resources/symlinks.py` — symlink deployment; its `TREES` is what sends `apps/` to `~/.local/bin/`
- `src/dotfiles/providers/custom.py` — personal tool installers
