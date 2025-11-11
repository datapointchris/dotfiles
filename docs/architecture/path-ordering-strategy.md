# PATH Ordering Strategy

**Purpose**: Define clear priority order for executable resolution across all platforms

## Priority Order (Highest to Lowest)

PATH elements are **prepended** in reverse order, so the last `add_path` call has highest priority.

```bash
# Execution priority (first match wins):
1. /usr/local/sbin           # Homebrew system daemons (macOS)
2. /usr/local/bin            # Homebrew/system-wide installs
3. /usr/bin                  # System packages (lowest priority)
4. ~/go/bin                  # Go-installed binaries (sess, toolbox)
5. /usr/local/go/bin         # Go toolchain (Linux)
6. /opt/nvim/bin             # Neovim extracted location (Linux)
7. /snap/bin                 # Snap packages (Linux)
8. ~/.local/share/npm/bin    # npm global packages (macOS)
9. /usr/local/opt/.../bin    # Homebrew formula-specific paths (macOS)
10. $ZSH_PLUGINS_DIR/forgit/bin  # Shell plugin binaries
11. ~/.local/bin             # USER TOOLS - Highest priority!
12. ~/.cargo/bin             # Rust/cargo tools - HIGHEST priority!
```

## Rationale

### Tier 1: Language Package Managers (Priority 12-11)

**~/.cargo/bin** (Highest)

- **Why first**: Latest versions of CLI tools (bat, fd, eza, delta, zoxide)
- **What's here**: Rust tools installed via cargo-binstall
- **Override**: Takes precedence over everything (we want latest)

**~/.local/bin** (Second highest)

- **Why here**: User-installed tools and scripts
- **What's here**: neovim, lazygit, yq, fzf, yazi, custom scripts, theme-sync, toolbox
- **Override**: User tools override system packages

### Tier 2: Development Tools (Priority 10-7)

**$ZSH_PLUGINS_DIR/forgit/bin**

- **Why here**: Shell-specific Git utilities
- **What's here**: forgit Git commands

**/usr/local/opt/.../bin** (macOS only)

- **Why here**: Homebrew formula-specific binaries
- **What's here**: postgresql@16, version-specific tools

**~/.local/share/npm/bin** (macOS only)

- **Why here**: npm global packages
- **What's here**: TypeScript, ESLint, Prettier, language servers

**/snap/bin** (Linux only)

- **Why here**: Snap-packaged applications
- **What's here**: Alternative installation method (rarely used in our setup)

**/opt/nvim/bin** (Linux only)

- **Why here**: Neovim extracted location (symlinked to ~/.local/bin)
- **Note**: Kept for direct access if symlink breaks

**/usr/local/go/bin** (Linux only)

- **Why here**: Go toolchain for building fzf
- **What's here**: go, gofmt, etc.

**~/go/bin**

- **Why here**: User-compiled Go binaries
- **What's here**: sess, toolbox (our Go CLI apps)

### Tier 3: System (Priority 3-1)

**/usr/bin** (Lowest priority)

- **Why last**: System packages, most conservative
- **What's here**: apt-installed packages (zsh, tmux, basic utilities)
- **Override**: Everything overrides this

**/usr/local/bin** (Second lowest)

- **Why here**: Homebrew/manually installed system-wide tools
- **What's here**: Homebrew packages (macOS)

**/usr/local/sbin** (Third lowest)

- **Why here**: System daemons and admin tools
- **What's here**: Homebrew services (macOS)

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
