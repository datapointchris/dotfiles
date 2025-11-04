# First Configuration

Essential configuration steps after installing dotfiles. Get your environment personalized in 10 minutes.

## Configure Git Identity

Set your Git name and email. This is required for commits.

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

**Verify**:

```bash
git config --global user.name
git config --global user.email
```

!!! tip "Platform-Specific Git Configs"
    The dotfiles use platform-specific Git configurations:

    - macOS: `~/.gitconfig` includes `macos/.gitconfig`
    - WSL: `~/.gitconfig` includes `wsl/.gitconfig`

    This allows different editors, credential helpers, and settings per platform.

---

## Choose Your Theme

The dotfiles come with **12 Base16 favorite themes**. Try a few to find your preference.

### List Available Themes

```bash
theme-sync favorites
```

**Output**:

```text
Available Favorite Themes:
  base16-rose-pine (current)
  base16-rose-pine-moon
  base16-gruvbox-dark-hard
  base16-kanagawa
  base16-oceanicnext
  base16-github-dark
  base16-nord
  base16-selenized-dark
  base16-everforest-dark-hard
  base16-tomorrow-night
  base16-tomorrow-night-eighties
```

### Apply a Theme

```bash
theme-sync apply base16-gruvbox-dark-hard
```

This synchronizes colors across:

- **tmux** (status bar, pane borders)
- **bat** (syntax highlighting)
- **fzf** (fuzzy finder)
- **shell** (LS_COLORS, prompt)

!!! info "Ghostty Themes"
    Ghostty uses a separate theme system with 600+ themes. Use:

    ```bash
    ghostty-theme --current                  # Show current
    ghostty-theme "Rose Pine"                # Apply theme
    ```

    The parallel systems approach gives you flexibility.

### Try Random Themes

```bash
theme-sync random
```

Applies a random favorite theme. Great for discovering new color schemes!

### Restore Default

```bash
theme-sync apply base16-rose-pine
```

---

## Explore Installed Tools

You have 31 CLI tools installed. Here's how to discover them.

### List All Tools

```bash
tools list
```

**Sample output**:

```text
Installed Tools (31 total)

  bat                       [file-viewer] Syntax-highlighting cat replacement
  eza                       [file-management] Modern ls replacement with git integration
  fd                        [search] Fast, user-friendly find alternative
  ripgrep                   [search] Ultra-fast recursive search tool
  ...
```

### Get Detailed Info

```bash
tools show bat
```

Shows:

- Description and why you'd use it
- Usage syntax
- Examples with explanations
- Related tools
- Documentation links

### Search for Tools

```bash
# Find git-related tools
tools search git

# Find file management tools
tools search file
```

### Discover Random Tools

```bash
tools random
```

Displays a random tool with full details. Run multiple times to discover your toolkit!

### Browse by Category

```bash
# List all categories
tools categories

# Count tools per category
tools count
```

---

## Customize Your Shell

The default shell configuration includes many conveniences. Customize further:

### Aliases

Located in `common/.shell/aliases.sh`:

```bash
# Edit aliases
nvim ~/dotfiles/common/.shell/aliases.sh

# Reload shell
source ~/.zshrc
```

**Common aliases already configured**:

```bash
ll          # eza -la (detailed list)
lt          # eza --tree (tree view)
cat         # bat (syntax highlighting)
find        # fd (faster find)
grep        # rg (ripgrep)
```

### Functions

Located in `macos/.shell/macos-functions.sh` (or platform-specific):

```bash
# Edit functions
nvim ~/dotfiles/macos/.shell/macos-functions.sh

# Reload shell
source ~/.zshrc
```

**Useful functions**:

- `mkcd` - Create and enter directory
- `extract` - Extract any archive type
- `backup` - Backup file with timestamp

### Custom Prompt

The prompt is configured in `.zshrc`. It shows:

- Current directory (shortened)
- Git branch and status
- Time (optional)
- Platform indicator

Customize in `common/.config/zsh/.zshrc`.

---

## Set Up Neovim

Neovim is configured with native LSP and modern plugins.

### First Launch

```bash
nvim
```

**First time**: Plugins will install automatically (lazy.nvim). Wait for completion.

### Configure LSP

LSP servers are pre-configured for 20+ languages. Most are installed via npm:

```bash
# Check installed LSPs
npm list -g --depth=0 | grep language-server
```

**If missing an LSP**:

```bash
# Install additional LSPs via npm
npm install -g <language>-language-server
```

See [Neovim Configuration](../configuration/neovim.md) for details.

### Choose Colorscheme

Neovim has a smart colorscheme manager that persists per Git project.

```bash
# In Neovim, use the Telescope picker
:Telescope colorscheme
```

Select a scheme. It will be saved for the current Git repository.

**Available schemes**:

- rose-pine
- gruvbox
- kanagawa
- catppuccin
- nord
- tokyo-night
- and more!

---

## Configure Tmux

Tmux is configured with modern keybindings and theme integration.

### Key Bindings

**Prefix**: `Ctrl + a` (not default `Ctrl + b`)

**Common commands**:

```bash
Ctrl+a c        # New window
Ctrl+a |        # Split vertical
Ctrl+a -        # Split horizontal
Ctrl+a h/j/k/l  # Navigate panes (vim-like)
Ctrl+a x        # Kill pane
Ctrl+a &        # Kill window
```

### Reload Config

After editing `common/.config/tmux/tmux.conf`:

```bash
# Inside tmux
Ctrl+a r

# Or from command line
tmux source-file ~/.config/tmux/tmux.conf
```

### Theme Synchronization

Tmux themes sync automatically with `theme-sync`:

```bash
theme-sync apply base16-nord
# Tmux reloads automatically
```

---

## Verify Everything Works

Run through this checklist to ensure everything is configured:

### System Checks

```bash
# Package managers
which brew || which apt || which pacman        # Package manager exists
task --version                                 # Taskfile installed

# Version managers
nvm --version                                  # nvm installed
uv --version                                   # uv installed
```

### Tool Checks

```bash
# Core tools
bat --version
eza --version
fd --version
rg --version
fzf --version

# Git tools
lazygit --version
delta --version

# Theme system
theme-sync current
```

### Configuration Checks

```bash
# Git identity
git config user.name
git config user.email

# Shell
echo $SHELL                    # Should be /bin/zsh
which zsh                      # Zsh installed

# PATH
echo $PATH | grep ".local/bin" # ~/.local/bin in PATH
```

### Neovim Checks

```bash
# Launch Neovim
nvim --version                 # v0.11+

# Check LSP (inside Neovim)
:checkhealth                   # Run health checks
:LspInfo                       # Show attached LSPs
```

!!! success "All Checks Pass"
    If all checks pass, your environment is fully configured!

!!! warning "Some Checks Fail"
    See [Troubleshooting Guide](../reference/troubleshooting.md) for solutions.

---

## Learn Task Automation

Taskfile provides 130+ automated tasks. Here are the most useful:

### Common Tasks

```bash
# Show all tasks
task --list

# Update all packages
task update

# Clean caches
task clean

# Verify installation
task verify
```

### Brew Tasks (macOS)

```bash
# Update Homebrew
task brew:update

# Install all Brewfile packages
task brew:install-all

# Show Brew info
task brew:info
```

### Theme Tasks

```bash
# Apply theme
task themes:rose-pine
task themes:gruvbox

# List themes
task themes:list

# Verify theme system
task themes:verify
```

### Symlink Tasks

```bash
# Verify symlinks
task symlinks:verify

# Relink (after adding files)
task symlinks:relink
```

**Full reference**: [Taskfile Reference](../reference/taskfile.md)

---

## Next Steps

Your environment is now configured! Continue exploring:

1. **Understand the Architecture**: [Architecture Overview](../architecture/index.md)
2. **Customize Further**: [Configuration Guide](../configuration/themes.md)
3. **Learn the Tools**: [Tool Registry](../reference/tools.md)
4. **Set Up Workflow**: [Workflow Guide](../configuration/workflow.md)

---

**Questions?** → [Troubleshooting Guide](../reference/troubleshooting.md)

**Want to contribute?** → [Testing Guide](../development/testing.md)
