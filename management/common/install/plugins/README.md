# Plugin Installers

## Pattern

This directory contains installers for editor and shell plugins (Neovim, Tmux, shell plugins). These scripts bootstrap plugin managers and install plugins from configuration files.

**Key characteristics**:

- Install plugin managers (Lazy.nvim, TPM, etc.)
- Trigger plugin installation via plugin managers
- Read plugin lists from configuration files or packages.yml
- One-time setup (plugins update themselves after initial install)

## When to Use

Add a new installer to this directory when:

- Installing a plugin manager for an editor or shell
- Bootstrapping a plugin system
- Installing multiple plugins from a configuration file
- Setting up shell enhancements (zsh plugins, tmux plugins)

## Libraries Used

Scripts in this directory typically source:

```bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"  # For error reporting
```

## Standard Patterns

### Pattern A: Plugin Manager Bootstrap

Install a plugin manager itself (Lazy.nvim, TPM):

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

PLUGIN_MANAGER_DIR="$HOME/.local/share/plugin-manager"

print_banner "Installing Plugin Manager"

if [[ -d "$PLUGIN_MANAGER_DIR" ]]; then
  log_success "Plugin manager already installed"
  exit 0
fi

log_info "Cloning plugin manager..."
if ! git clone https://github.com/user/plugin-manager.git "$PLUGIN_MANAGER_DIR"; then
  manual_steps="Manual installation:
1. Clone: git clone https://github.com/user/plugin-manager.git $PLUGIN_MANAGER_DIR
2. Verify: ls $PLUGIN_MANAGER_DIR"
  output_failure_data "plugin-manager" "https://github.com/user/plugin-manager" "latest" "$manual_steps" "git clone failed"
  log_error "Installation failed"
  exit 1
fi

log_success "Plugin manager installed"
```

### Pattern B: Plugin Installation

Trigger plugin installation via plugin manager:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Installing Plugins"

# Method 1: Editor headless mode
if ! nvim --headless "+Lazy! sync" +qa; then
  log_warning "Some plugins may have failed to install"
  log_info "Run :Lazy sync in Neovim to retry"
fi

# Method 2: Plugin manager install script
tmux start-server
tmux new-session -d
~/.tmux/plugins/tpm/scripts/install_plugins.sh
tmux kill-server

log_success "Plugins installed"
```

### Pattern C: Shell Plugin Installation

Install shell plugins from packages.yml:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.local/share/zsh/plugins}"
mkdir -p "$ZSH_CUSTOM"

print_banner "Installing Shell Plugins"

# Read plugins from packages.yml (name|repo format)
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=shell-plugins --format=name_repo | while IFS='|' read -r name repo; do
  PLUGIN_DIR="$ZSH_CUSTOM/$name"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_info "$name already installed"
    continue
  fi

  log_info "Installing $name..."
  if git clone "https://github.com/$repo.git" "$PLUGIN_DIR"; then
    log_success "$name installed"
  else
    manual_steps="Clone manually: git clone https://github.com/$repo.git $PLUGIN_DIR"
    output_failure_data "$name" "https://github.com/$repo" "latest" "$manual_steps" "git clone failed"
    log_warning "$name installation failed"
  fi
done

log_success "Shell plugins installed"
```

## Adding a New Plugin Manager

1. **Identify plugin manager type**:
   - Git clone (most common)
   - Download binary
   - Install via language package manager

2. **Find installation directory**:
   - Neovim: `~/.local/share/nvim/`
   - Tmux: `~/.tmux/plugins/`
   - Zsh: `~/.local/share/zsh/plugins/`

3. **Create new script** named `{tool}-plugins.sh`

4. **Implement idempotency check**:

   ```bash
   if [[ -d "$PLUGIN_DIR" ]]; then
     log_success "already installed"
     exit 0
   fi
   ```

5. **Add installation logic**:

   ```bash
   if ! git clone https://... "$PLUGIN_DIR"; then
     output_failure_data ...
     exit 1
   fi
   ```

6. **Test**:

   ```bash
   bash management/common/install/plugins/{tool}-plugins.sh
   ls $PLUGIN_DIR
   # Test idempotency
   bash management/common/install/plugins/{tool}-plugins.sh
   ```

## Examples

### Neovim plugins (nvim-plugins.sh)

```bash
LAZY_NVIM="$HOME/.local/share/nvim/lazy/lazy.nvim"

print_banner "Installing Neovim Plugins"

# Install Lazy.nvim plugin manager if not present
if [[ ! -d "$LAZY_NVIM" ]]; then
  log_info "Installing Lazy.nvim plugin manager..."
  if ! git clone --filter=blob:none https://github.com/folke/lazy.nvim.git --branch=stable "$LAZY_NVIM"; then
    manual_steps="1. Clone Lazy.nvim: git clone https://github.com/folke/lazy.nvim.git ~/.local/share/nvim/lazy/lazy.nvim
2. Open Neovim: nvim
3. Plugins will auto-install"
    output_failure_data "lazy.nvim" "https://github.com/folke/lazy.nvim" "stable" "$manual_steps" "git clone failed"
    log_error "Failed to install Lazy.nvim"
    exit 1
  fi
fi

# Trigger plugin installation via Neovim headless mode
log_info "Installing Neovim plugins..."
if nvim --headless "+Lazy! sync" +qa 2>&1 | grep -q "Error"; then
  log_warning "Some plugins may have failed"
  log_info "Open Neovim and run :Lazy sync to retry"
else
  log_success "Neovim plugins installed"
fi
```

### Tmux plugins (tmux-plugins.sh)

```bash
TPM_DIR="$HOME/.tmux/plugins/tpm"

print_banner "Installing Tmux Plugin Manager"

if [[ ! -d "$TPM_DIR" ]]; then
  log_info "Installing TPM..."
  if ! git clone https://github.com/tmux-plugins/tpm "$TPM_DIR"; then
    manual_steps="1. Clone TPM: git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
2. Start tmux: tmux
3. Press prefix + I to install plugins"
    output_failure_data "tpm" "https://github.com/tmux-plugins/tpm" "latest" "$manual_steps" "git clone failed"
    exit 1
  fi
fi

# Install tmux plugins
log_info "Installing tmux plugins..."
if [[ -f "$TPM_DIR/scripts/install_plugins.sh" ]]; then
  # TPM install script requires tmux server running
  tmux start-server
  tmux new-session -d
  "$TPM_DIR/scripts/install_plugins.sh"
  tmux kill-server
  log_success "Tmux plugins installed"
else
  log_warning "TPM install script not found, plugins will install on first tmux launch"
fi
```

### Shell plugins (shell-plugins.sh)

```bash
ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.local/share/zsh/plugins}"
mkdir -p "$ZSH_CUSTOM"

print_banner "Installing Shell Plugins"

# Parse shell plugins from packages.yml (returns "name|repo" pairs)
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=shell-plugins --format=name_repo | while IFS='|' read -r name repo; do
  PLUGIN_DIR="$ZSH_CUSTOM/$name"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_info "$name already installed"
    continue
  fi

  log_info "Installing $name..."
  if git clone "https://github.com/$repo.git" "$PLUGIN_DIR"; then
    log_success "$name installed"
  else
    manual_steps="Clone plugin manually:
   git clone https://github.com/$repo.git $PLUGIN_DIR

Then source in .zshrc:
   source $PLUGIN_DIR/{plugin-file}.zsh"
    output_failure_data "$name" "https://github.com/$repo" "latest" "$manual_steps" "git clone failed"
    log_warning "$name installation failed"
  fi
done
```

## Plugin Configuration

Plugins are typically configured in:

- **Neovim**: `~/.config/nvim/lua/plugins/` (Lazy.nvim reads these)
- **Tmux**: `~/.config/tmux/tmux.conf` (lists TPM plugins)
- **Shell**: `packages.yml` (shell_plugins section)

### Adding plugins to packages.yml

```yaml
shell_plugins:
  - name: zsh-syntax-highlighting
    repo: zsh-users/zsh-syntax-highlighting
  - name: zsh-autosuggestions
    repo: zsh-users/zsh-autosuggestions
```

## Error Handling

Plugin installers handle errors by:

- Checking if plugin manager is installed first
- Reporting git clone failures
- Providing manual installation instructions
- Allowing plugin managers to retry failed plugins

## Important Notes

1. **Plugin managers install plugins**: These scripts install the plugin manager, the manager installs individual plugins

2. **Headless mode**: Editor plugins often install via headless mode (nvim --headless)

3. **Configuration files**: Plugin managers read plugin lists from config files

4. **Updates**: Plugins typically update themselves (`:Lazy update`, `prefix + U`)

5. **Idempotency**: Check if plugin manager directory exists before cloning

## Common Issues

**Issue**: Plugins fail to install

- **Solution**: Plugin manager installed but plugins need manual trigger

**Issue**: Headless mode hangs

- **Solution**: Timeout or bad plugin specification in config

**Issue**: Permission denied

- **Solution**: Check directory permissions, ensure user owns plugin directories

**Issue**: Git clone fails

- **Solution**: Network issue, provide manual clone instructions

**Issue**: Plugin manager not found

- **Solution**: Ensure plugin manager script ran first
