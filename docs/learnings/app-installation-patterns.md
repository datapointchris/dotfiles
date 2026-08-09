# App Installation Patterns

**Context**: Managing custom CLI apps with different installation methods.

## Four App Categories

### 1. Go Apps (Remote Install via `go install`)

**Examples**: `todoui`, `toolbox`

**Installation**: Installed from GitHub via `go install` in packages.yml:

```yaml
go_tools:
  - name: todoui
    package: github.com/datapointchris/todoui
  - name: toolbox
    package: github.com/datapointchris/toolbox
```

**Development**: Source code lives in `~/tools/todoui/` and `~/tools/toolbox/`. Changes are tested locally with `go run .` or `go build`, then pushed to GitHub. Fresh installs get the latest from GitHub.

**Binary location**: `~/go/bin/`

### 2. Shell Script Apps (Symlink Pattern)

**Examples**: `notes`, `packup`, `aws-profiles`

**Location**: `apps/common/`, plus `apps/<axis>/<value>/` for one that only makes
sense at a coordinate — the rofi menus are under `apps/display/wayland/`.

**Installation**: every layer the machine's coordinates select is symlinked into
`~/.local/bin/` by `dotfiles symlinks apply`. Directories are skipped, so only
executable files are linked, and the layers flatten onto one destination because
a command has to be on `PATH` rather than under a directory naming why it exists.

**An app that has to change the calling shell is two pieces: a command and a function.** A
subprocess cannot export a variable into the shell that ran it, so anything setting `AWS_PROFILE`,
`PATH` or the like needs a shell function — and that function belongs in `shell/common/functions.sh`
with the other forty, not in `apps/`. The command does the work and prints a decision; the function
evals or reads it and does the exporting. This is how `zoxide init`, `fnm env` and `atuin init` are
wired in `.zshrc`, and `aws-profiles` is the in-repo example: `_aws-profiles` draws the menu on
stderr and prints its choice on stdout, and the `aws-profiles` function exports it.

The underscore marks the half that is not the way in. It is safe in `~/.local/bin` — the `_name`
convention that would collide is zsh's completion functions, which live in `fpath`, not `PATH`.

The alternative this replaced was a *sourced* app plus `alias aws-profiles='source ...'`. It worked,
but only on the one platform where somebody remembered to write the alias; everywhere else the
command ran in its own process, said it had set the profile, and exited having set nothing. A
function cannot be invoked the wrong way, which is the real reason to prefer it.

### 3. Personal CLI Tools (Git Clone Pattern)

**Examples**: `theme`, `font`

**Installation**: `src/dotfiles/providers/custom.py` runs the vendor's own install script, which clones from GitHub to `~/.local/share/` and symlinks its bin into `~/.local/bin/`. Once the checkout exists, converging means delegating to the tool's own `update` rather than re-running the installer over a live checkout.

**Development**: Source code in `~/tools/theme/` and `~/tools/font/`. Changes tested locally, pushed to GitHub. Run `theme update` or `font update` to pull updates to installed version.

**Update**: Built-in `update` command runs `git pull` on the installed version.

### 4. Python Tools (Remote Install via `uv tool install`)

**Examples**: `relate`, `logsift`, `indy`, `refcheck`, `syncer`, `safekeep`

**Installation**: Installed from GitHub via `uv tool install`, pinned to the repo's newest release tag, from packages.yml:

```yaml
git_uv_tools:
  - name: relate
    repo: https://github.com/datapointchris/relate.git
  - name: keymap-align
    repo: https://github.com/datapointchris/keymap-align.git
    tracks_branch: true    # publishes no releases, so there is no tag to pin
```

The pin is not optional. Each of these tools carries `pyselfupdate`, which reads uv's receipt to decide what it may do: a git requirement with no `rev=` is treated as a dev checkout, so the tool never prints an update notice and refuses to reinstall over itself. And once a receipt *is* pinned, `uv tool upgrade` re-resolves the pin to the same commit forever and reports "already at latest" however far behind it is. See `install/common/lib/uv-git-tools.sh`.

**Development**: Source code lives in `~/tools/{app}/`. Changes are tested locally, then pushed to GitHub — and a release must be cut for the fleet to pick them up, since the install tracks release tags rather than `main`.

**Binary location**: `~/.local/bin/` (managed by uv)

## Directory Summary

| Category | Development | Installed | Binary/Symlink |
| --- | --- | --- | --- |
| Go apps | ~/tools/{app}/ | GitHub | ~/go/bin/{app} |
| Shell scripts | apps/common/ or apps/{axis}/{value}/ | (same) | ~/.local/bin/{app} → repo |
| Personal tools | ~/tools/{app}/ | ~/.local/share/{app}/ | ~/.local/bin/{app} → .local/share |
| Python tools | ~/tools/{app}/ | GitHub | ~/.local/bin/{app} (uv-managed) |

## PATH Requirements

Both directories must be in PATH (configured in `.zshrc`):

```bash
export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"
```

## Key Learnings

1. **Go apps install from GitHub** - Use `go install`, not local builds
2. **Shell scripts are symlinked** - Direct link from repo to ~/.local/bin
3. **Personal tools separate dev from installed** - ~/tools/ for dev, ~/.local/share/ for installed
4. **Upgrade commands are self-contained** - Tools manage their own updates via `git pull`

## Related Files

- `install/packages.yml` - Go tools list
- `src/dotfiles/symlinks/core.py` - Symlink management (apps linked via `create_symlinks` to `~/.local/bin/`)
- `src/dotfiles/providers/custom.py` - Personal tool installers
- `configs/common/.config/zsh/.zshrc` - PATH configuration
