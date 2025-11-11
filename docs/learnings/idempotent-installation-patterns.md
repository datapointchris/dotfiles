# Idempotent Installation Patterns

**Context**: Installation scripts must be re-runnable to add new components (plugins, packages, themes) without breaking existing installations.

## The Problem

Installation scripts that exit early when the main binary is installed will skip sub-components (plugins, flavors, packages), creating silent failures and preventing updates:

```bash
# BAD: Exits early, skips plugins forever
if command -v yazi >/dev/null 2>&1; then
  echo "Yazi already installed"
  exit 0  # PROBLEM: Never installs plugins/flavors
fi

# Install plugins...
ya pkg add some-plugin
```

**Symptoms**:

- Initial installation fails silently (plugin install error hidden)
- Re-running install doesn't fix missing plugins
- Adding new plugins to script has no effect
- "Already installed" message but components missing

## Root Causes

**1. Early Exit in Scripts**
Scripts check for binary and exit before installing sub-components

**2. Taskfile `status:` Checks**
Task's `status:` field prevents task from running if binary exists

**3. Combination of Both**
Redundant checks create double-skip behavior

## The Solution

**For installations with sub-components (yazi, npm, cargo):**

1. **Remove `status:` check from Taskfile** - Always run the script
2. **Script checks binary, continues to components** - Don't exit early
3. **Make component installation idempotent** - Safe to run multiple times

```yaml
# GOOD: No status check, always runs
install-yazi:
  desc: Install yazi terminal file manager with flavors and plugins
  cmds:
    - bash management/taskfiles/scripts/install-yazi.sh
  # Note: No status check - always run to ensure plugins/flavors are up to date
```

```bash
# GOOD: Checks binary, but continues to plugins
if ! command -v yazi >/dev/null 2>&1; then
  echo "Installing yazi binary..."
  # Install binary
else
  echo "Yazi binary already installed"
fi

# ALWAYS run plugin installation (ya pkg add is idempotent)
echo "Installing yazi plugins..."
ya pkg add AnirudhG07/nbpreview
ya pkg add pirafrank/what-size
```

**For simple binary installations (yq, lazygit, uv):**

1. **Keep `status:` check in Taskfile** - Skip if installed
2. **Remove redundant `if command -v... exit 0`** - Task handles this

```yaml
# GOOD: Task's status check is sufficient
install-lazygit:
  desc: Install lazygit from GitHub releases
  cmds:
    - |
      echo "Installing lazygit..."
      # Download and install
  status:
    - command -v lazygit >/dev/null 2>&1
```

**For packages with individual components (npm, cargo):**

Use the check-then-install pattern for each package:

```bash
# GOOD: Check each package individually
install_if_missing() {
  local package=$1
  local command_name=${2:-$package}

  if command -v "$command_name" >/dev/null 2>&1; then
    echo "  $package already installed, skipping"
  else
    echo "  Installing $package..."
    npm install -g "$package"
  fi
}

install_if_missing typescript-language-server
install_if_missing bash-language-server
```

## Key Learnings

1. **Installation scripts must be re-runnable** - Adding new components should work
2. **Don't hide failures with early exits** - Silent failures are landmines
3. **Task's `status:` vs script checks** - Understand which layer handles skipping
4. **Idempotent operations are safe** - `ya pkg add` won't reinstall existing plugins
5. **Never use `|| echo "Failed (continuing)"`** - Masks real errors

## Testing

After fixing, verify:

- Re-running install adds new plugins/packages
- Existing installations aren't broken
- Errors stop execution immediately
- "Already installed" messages are accurate

## Related Files

- `management/taskfiles/scripts/install-yazi.sh` - Yazi with plugins/flavors
- `management/taskfiles/scripts/npm-install-globals.sh` - Good pattern example
- `management/taskfiles/wsl.yml:install-cargo-tools` - Individual package checks
- `management/taskfiles/wsl.yml:install-yazi` - No status check pattern
