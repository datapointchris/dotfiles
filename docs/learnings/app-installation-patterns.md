# App Installation Patterns

**Context**: Managing custom CLI apps across platforms with different installation methods.

## The Problem

Confusion between Go apps (directories with source) vs shell script apps (executable files) leading to incorrect symlink expectations and installation failures.

## Two Distinct App Types

### 1. Go Apps (Build + Install Pattern)

**Location**: `apps/common/{app}/` (directories)

**Characteristics**:

- Are DIRECTORIES containing Go source code
- Have a `Taskfile.yml` with `install` task
- Build process: `go build` → `cp binary ~/go/bin/`
- **NEVER symlinked** - they install themselves to `~/go/bin`

**Examples**: `sess/`, `toolbox/`

**Installation** (in main Taskfile.yml):

```yaml
- echo "Building Go apps..."
- cd apps/common/sess && task install
- cd apps/common/toolbox && task install
```

### 2. Shell Script Apps (Symlink Pattern)

**Location**: `apps/{platform}/` (files)

**Characteristics**:

- Are EXECUTABLE FILES (not directories)
- Symlinked from `apps/{platform}/` → `~/.local/bin/`
- Handled by `link_apps()` in symlinks manager
- `link_apps()` skips directories, only symlinks files

**Examples**: `menu`, `notes`, `theme-sync`, `bashbox`, `printcolors`

**Installation** (in symlinks manager `cli.py`):

```python
manager.link_apps("common")  # Symlinks apps/common/* files
manager.link_apps(platform)   # Symlinks apps/{platform}/* files
```

## Critical Implementation Details

**Symlink Manager Behavior**:

```python
def link_apps(self, platform: str):
    for app in apps_dir.iterdir():
        if app.is_dir():  # SKIP directories (Go apps)
            continue
        # Only symlink FILES
        target.symlink_to(relative_source)
```

**PATH Requirements**:
Both `~/.local/bin` and `~/go/bin` must be in PATH (configured in `.zshrc`):

```bash
export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"
```

## Testing

**Verification checks**:

- Go apps: `command -v toolbox` (finds in ~/go/bin)
- Shell apps: `command -v menu` (finds in ~/.local/bin via symlink)

## Key Learnings

1. **Go apps install themselves** - Don't try to symlink them
2. **Shell apps are symlinked** - Don't try to build them
3. **`link_apps()` only processes files** - Directories are intentionally skipped
4. **PATH must include both bin directories** - Or apps won't be found
5. **Don't confuse the two patterns** - They are fundamentally different installation methods

## Common Mistakes

❌ **Trying to symlink Go apps**: They're directories, not files - symlinks manager skips them
❌ **Trying to build shell scripts**: They're already executable - just symlink them
❌ **Not calling `link_apps()` in `link` command**: Apps won't get symlinked during installation
❌ **Forgetting PATH setup**: Apps won't be found even if installed correctly

## Related Files

- `Taskfile.yml` - Go app build steps
- `management/symlinks/symlinks/manager.py:link_apps()` - Shell app symlinking
- `management/symlinks/symlinks/cli.py:link()` - Calls both dotfiles + apps linking
- `platforms/common/.config/zsh/.zshrc` - PATH configuration
