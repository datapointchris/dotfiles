# PATH Ordering Strategy

**Purpose**: Define clear priority order for executable resolution across all platforms

## PATH Priority Order

Listed from highest to lowest priority. First match wins during command execution.

### `~/.cargo/bin`

- Rust tools installed via cargo-binstall (bat, fd, eza, delta, zoxide). Latest versions, takes precedence over everything.

### `~/.local/bin`

- User-installed tools and scripts (neovim, lazygit, yq, fzf, yazi, custom scripts, theme-sync, toolbox).

### `$ZSH_PLUGINS_DIR/forgit/bin`

- Shell-specific Git utilities (forgit commands).

### `/usr/local/opt/.../bin`

- Homebrew formula-specific binaries (postgresql@16, version-specific tools). macOS only.

### `~/.local/share/npm/bin`

- npm global packages (TypeScript, ESLint, Prettier, language servers). macOS only.

### `/snap/bin`

- Snap-packaged applications. Linux only.

### `/opt/nvim/bin`

- Neovim extracted location (symlinked to ~/.local/bin). Linux only.

### `/usr/local/go/bin`

- Go toolchain for building fzf (go, gofmt, etc.). Linux only.

### `~/go/bin`

- User-compiled Go binaries (sess, toolbox - our Go CLI apps).

### `/usr/bin`

- System packages (zsh, tmux, basic utilities). Lowest priority.

### `/usr/local/bin`

- Homebrew/manually installed system-wide tools. macOS only.

### `/usr/local/sbin`

- Homebrew system daemons and admin tools. macOS only.

## Implementation Pattern

```bash
# add_path PREPENDS, so reverse order (last call = highest priority)

# System (will be lowest priority)
add_path "/usr/bin"
add_path "/usr/local/bin"
add_path "/usr/local/sbin"

# Platform-specific development tools
if [[ "$OSTYPE" == "darwin"* ]]; then
    add_path "/usr/local/opt/postgresql@16/bin"
    add_path "~/.local/share/npm/bin"
    add_path "~/go/bin"
else
    # Linux
    add_path "/snap/bin"
    add_path "/opt/nvim/bin"
    add_path "/usr/local/go/bin"
    add_path "~/go/bin"
fi

# Common (will be higher priority)
add_path "$ZSH_PLUGINS_DIR/forgit/bin"
add_path "~/.local/bin"          # User tools
add_path "~/.cargo/bin"          # Rust tools (HIGHEST)
```

## Tool Resolution Examples

### Example 1: `bat` command

```bash
$ which bat
/Users/chris/.cargo/bin/bat  # cargo-binstall version (latest)

# Not: /usr/bin/batcat (apt version, older)
```

### Example 2: `nvim` command

```bash
$ which nvim
/Users/chris/.local/bin/nvim  # Symlink to latest GitHub release

# Not: /usr/bin/nvim (apt version 0.9.5, too old)
```

### Example 3: `fd` command

```bash
$ which fd
/Users/chris/.cargo/bin/fd  # cargo-binstall version (latest, correct name!)

# Not: /usr/bin/fdfind (apt version, wrong name)
```

### Example 4: `go` command

```bash
$ which go
/usr/local/go/bin/go  # Latest from go.dev

# Not: /usr/bin/go (apt version 1.22, outdated)
```

## Debugging PATH Issues

```bash
# Show current PATH in readable format
echo $PATH | tr ':' '\n' | nl

# Find all instances of a command
which -a nvim

# Show what would execute
type bat

# Full PATH info
echo $PATH
```

## Design Principles

1. **User space first**: `~/.cargo/bin` and `~/.local/bin` override everything
2. **Language ecosystems**: Each package manager has its own bin directory
3. **System packages last**: `/usr/bin` is lowest priority (stable but outdated)
4. **Platform-aware**: macOS and Linux have different requirements
5. **Explicit over implicit**: Clear why each directory is at its priority level

## Maintenance

When adding new PATH directories:

1. **Determine priority**: Does it need to override system or user tools?
2. **Add in correct position**: Remember add_path prepends
3. **Document rationale**: Update this file with why it's placed there
4. **Test resolution**: Use `which -a` to verify correct tool is found first

## Related Documents

- [Package Management Philosophy](package-management.md)
- [Package Version Analysis](../learnings/package-version-analysis.md)
- [App Installation Patterns](../learnings/app-installation-patterns.md)
