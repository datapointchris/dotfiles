# App Installation Patterns

**Context**: Managing custom CLI apps with different installation methods.

## Three App Categories

### 1. Go Apps (Remote Install via `go install`)

**Examples**: `sess`, `toolbox`

**Installation**: Installed from GitHub via `go install` in packages.yml:

```yaml
go_tools:
  - name: sess
    package: github.com/datapointchris/sess/cmd/sess
  - name: toolbox
    package: github.com/datapointchris/toolbox
```

**Development**: Source code lives in `~/tools/sess/` and `~/tools/toolbox/`. Changes are tested locally with `go run .` or `go build`, then pushed to GitHub. Fresh installs get the latest from GitHub.

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

**Development**: Source code in `~/tools/theme/` and `~/tools/font/`. Changes tested locally, pushed to GitHub. Run `theme upgrade` or `font upgrade` to pull updates to installed version.

**Upgrade**: Built-in `upgrade` command runs `git pull` on the installed version.

### 4. Python Tools (Remote Install via `uv tool install`)

**Examples**: `relate`, `logsift`, `indy`, `refcheck`, `syncer`

**Installation**: Installed from GitHub via `uv tool install` in packages.yml:

```yaml
git_uv_tools:
  - name: relate
    repo: https://github.com/datapointchris/relate.git
  - name: logsift
    repo: https://github.com/datapointchris/logsift.git
```

**Development**: Source code lives in `~/tools/{app}/`. Changes are tested locally, then pushed to GitHub. `uv tool install` gets the latest from GitHub.

**Binary location**: `~/.local/bin/` (managed by uv)

## Directory Summary

| Category | Development | Installed | Binary/Symlink |
|----------|-------------|-----------|----------------|
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
