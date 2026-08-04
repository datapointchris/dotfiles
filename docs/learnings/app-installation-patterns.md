# App Installation Patterns

**Context**: Managing custom CLI apps with different installation methods.

## Three App Categories

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

**Examples**: `menu`, `notes`, `aws-profiles`

**Location**: `apps/{platform}/` (executable files)

**Installation**: Symlinked from repo → `~/.local/bin/` by symlinks manager:

```python
create_symlinks(apps_dir / "common", "apps-common", target_dir=Path.home() / ".local/bin")
create_symlinks(apps_dir / platform, f"apps-{platform}", target_dir=Path.home() / ".local/bin")
```

`create_symlinks()` skips directories (via `rglob` + `is_file()`), so only executable files are linked.

### 3. Personal CLI Tools (Git Clone Pattern)

**Examples**: `theme`, `font`

**Installation**: Custom installers clone from GitHub to `~/.local/share/`, symlink bin to `~/.local/bin/`:

```bash
# In install/common/custom-installers/theme.sh
git clone https://github.com/datapointchris/theme.git ~/.local/share/theme
ln -sf ~/.local/share/theme/bin/theme ~/.local/bin/theme
```

**Development**: Source code in `~/tools/theme/` and `~/tools/font/`. Changes tested locally, pushed to GitHub. Run `theme update` or `font update` to pull updates to installed version.

**Update**: Built-in `update` command runs `git pull` on the installed version.

### 4. Python Tools (Remote Install via `uv tool install`)

**Examples**: `relate`, `logsift`, `indy`, `refcheck`, `syncer`

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
| Shell scripts | apps/{platform}/ | (same) | ~/.local/bin/{app} → repo |
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
- `symlinks/core.py` - Symlink management (apps linked via `create_symlinks` to `~/.local/bin/`)
- `install/common/custom-installers/theme.sh` - Personal tool installer
- `configs/common/.config/zsh/.zshrc` - PATH configuration
