#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"

export DOTFILES_DIR
export FAILURES_LOG
export TERM=${TERM:-xterm}
export PATH="$HOME/.local/bin:$PATH"

source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/run-installer.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/package-query.sh"

if [[ -f "$HOME/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$HOME/.env"
  set +a
fi

PHASE_VERB="install"
source "$DOTFILES_DIR/install/phases.sh"

# Resolved from the manifest in main(), before any phase runs.
PLATFORM=""

if [[ $EUID -eq 0 ]] && [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
  die "Do not run this script as root"
fi

# ================================================================
# MANIFEST HELPERS
# ================================================================

# Read a manifest field via parse_packages.py
manifest_field() {
  local field="$1"
  /usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
    --manifest-field="$field" --manifest="$MACHINE"
}

# Check if a manifest boolean field is true
manifest_enabled() {
  local field="$1"
  [[ "$(manifest_field "$field")" == "true" ]]
}

# System-package tier from the manifest: "core", "workstation", or "" (disabled).
# `system_packages: false` (or absent) disables the phase entirely; a tier name
# selects how much of packages.yml to install (see get_system_packages there).
manifest_system_tier() {
  local tier
  tier=$(manifest_field "system_packages" 2>/dev/null) || tier=""
  [[ "$tier" == "false" ]] && tier=""           # explicit disable
  [[ "$tier" == "true" ]] && tier="workstation" # legacy boolean = full set
  echo "$tier"
}

# ================================================================
# PHASES
# ================================================================
# One function per registry entry in install/phases.sh, in the order that file
# lists them. What each phase would act on is resolved by the items_<phase>
# functions there, which --dry-run prints and update shares.
#
# The tool lists come from parse_packages rather than the raw manifest key, so
# --mine narrows them. Reading the manifest directly is also a second source of
# truth for the same list: it is the manifest names alone, where parse_packages
# returns the manifest intersected with packages.yml.

INSTALL_COMMON="$DOTFILES_DIR/install/common"

install_system_packages() {
  local sys_tier
  sys_tier=$(manifest_system_tier)

  case "$PLATFORM" in
    macos)
      local macos="$DOTFILES_DIR/install/macos"

      print_header "System Tools (Homebrew)"
      bash "$macos/homebrew.sh"
      SYSTEM_PACKAGE_TIER="${sys_tier:-workstation}" bash "$macos/system-packages.sh"
      bash "$macos/casks.sh"
      bash "$macos/configure-docker.sh"
      bash "$macos/mas-apps.sh"
      bash "$macos/xcode.sh"

      print_header "System Preferences"
      bash "$macos/preferences.sh"
      ;;
    wsl)
      if ! grep -q "Microsoft" /proc/version 2>/dev/null && ! grep -q "WSL" /proc/version 2>/dev/null; then
        log_warning "Warning: This script is designed for WSL Ubuntu"
        log_warning "Continuing anyway..."
      fi

      if [[ -n "$sys_tier" ]]; then
        print_header "System Packages (apt)"
        SYSTEM_PACKAGE_TIER="$sys_tier" bash "$DOTFILES_DIR/install/wsl/system-packages.sh"
      fi

      print_section "WSL fontconfig setup"
      bash "$DOTFILES_DIR/install/wsl/fontconfig-setup.sh"
      ;;
    archlinux)
      if [[ -n "$sys_tier" ]]; then
        print_header "System Packages (pacman)"
        SYSTEM_PACKAGE_TIER="$sys_tier" bash "$DOTFILES_DIR/install/archlinux/system-packages.sh"
      fi
      if manifest_enabled "flatpak"; then
        bash "$DOTFILES_DIR/install/archlinux/flatpak.sh"
      fi

      print_header "System Configuration"
      bash "$DOTFILES_DIR/install/archlinux/system-config.sh"
      ;;
    linux)
      # Generic Debian/Ubuntu Linux — the minimal LXC/small-box target. No GUI,
      # flatpak, or OS-preference steps; the manifest's tier (typically "core")
      # keeps the apt payload lean.
      if [[ -n "$sys_tier" ]]; then
        print_header "System Packages (apt)"
        SYSTEM_PACKAGE_TIER="$sys_tier" bash "$DOTFILES_DIR/install/linux/system-packages.sh"
      fi
      ;;
    *)
      die "Unsupported platform: $PLATFORM"
      ;;
  esac
}

install_go_toolchain() {
  packages_present --type=go || return 0
  print_header "Go Toolchain"
  run_installer "$INSTALL_COMMON/language-managers/go.sh" "go"
}

install_rust_toolchain() {
  packages_present --type=cargo || return 0
  print_header "Rust Toolchain"
  run_installer "$INSTALL_COMMON/language-managers/rust.sh" "rust"
  run_installer "$INSTALL_COMMON/language-tools/cargo-binstall.sh" "cargo-binstall"
}

# Ungated, unlike every other toolchain: the symlink phase runs `uv run
# symlinks`, so a manifest with empty uv lists (linux-lxc-server) still needs uv
# or symlinking dies with exit 127 and no dotfiles get linked.
install_uv() {
  print_header "uv"
  run_installer "$INSTALL_COMMON/language-managers/uv.sh" "uv"
}

install_go_tools() {
  packages_present --type=go || return 0
  print_header "Go Tools"
  PATH="/usr/local/go/bin:$PATH" run_installer "$INSTALL_COMMON/language-tools/go-tools.sh" "go-tools"
}

# The github-release and custom-installer phases are a directory of per-tool
# scripts rather than one script over a list, so the loop lives here.
run_script_backed_phase() {
  local header="$1" script_dir="$2" kind="$3"
  shift 3

  local tools
  tools=$(parse_packages "$@") || return 0
  [[ -n "$tools" ]] || return 0

  print_header "$header"
  local tool script
  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    script="$script_dir/${tool}.sh"
    if [[ -f "$script" ]]; then
      run_installer "$script" "$tool"
    else
      log_warning "No installer script for $kind: $tool (packages verify should have caught this)"
    fi
  done <<<"$tools"
}

install_github_releases() {
  run_script_backed_phase "GitHub Release Tools" \
    "$INSTALL_COMMON/github-releases" "github release" --type=github
}

install_custom_installers() {
  run_script_backed_phase "Custom Distribution Tools" \
    "$INSTALL_COMMON/custom-installers" "custom installer" --type=custom
}

install_cargo_packages() {
  packages_present --type=cargo || return 0
  print_header "Rust/Cargo Tools"
  run_installer "$INSTALL_COMMON/language-tools/cargo-tools.sh" "cargo-tools"
}

# Runs after cargo packages, which is where fnm comes from, and before npm
# globals, so those install against the fleet's Node rather than whatever the
# system package happens to be.
install_node_toolchain() {
  packages_present --type=npm || return 0
  print_header "Node Toolchain"
  run_installer "$INSTALL_COMMON/language-managers/node.sh" "node"
}

install_npm_globals() {
  packages_present --type=npm || return 0
  print_header "npm Globals"
  run_installer "$INSTALL_COMMON/language-tools/npm-install-globals.sh" "npm-globals"
}

install_uv_tools() {
  packages_present --type=uv || packages_present --type=git_uv || return 0
  print_header "Python Tools (uv)"
  run_installer "$INSTALL_COMMON/language-tools/uv-tools.sh" "uv-tools"
}

install_shell_plugins() {
  manifest_enabled "shell_plugins" || return 0
  print_header "Shell Plugins"
  run_installer "$INSTALL_COMMON/plugins/shell-plugins.sh" "shell-plugins"
}

install_symlinks() {
  print_header "Symlinking Dotfiles"
  cd "$DOTFILES_DIR" && PATH="$HOME/go/bin:$PATH" task symlinks:relink

  # Hyprland reads the config files this phase just deployed, so the reload
  # belongs here rather than at the end of the run.
  if [[ "$PLATFORM" == "archlinux" ]] && command -v hyprctl &>/dev/null; then
    print_section "Reloading Hyprland configuration"
    hyprctl reload
    log_success "Hyprland configuration reloaded"
  fi
}

install_tmux_plugins() {
  manifest_enabled "tmux_plugins" || return 0
  print_header "Tmux Plugins"
  run_installer "$INSTALL_COMMON/plugins/tpm.sh" "tpm"
  run_installer "$INSTALL_COMMON/plugins/tmux-plugins.sh" "tmux-plugins"
}

install_nvim_plugins() {
  manifest_enabled "nvim_plugins" || return 0
  print_header "Neovim Plugins"
  run_installer "$INSTALL_COMMON/plugins/nvim-plugins.sh" "nvim-plugins"
}

# Runs on all platforms: setting ZDOTDIR in the system zshenv is what macOS
# needs for its XDG zsh config to load, while the chsh self-skips where zsh is
# already the default (i.e. macOS).
install_zsh_config() {
  manifest_enabled "configure_zsh" || return 0
  print_header "Post-Installation Configuration"
  print_section "Configuring ZSH"
  ensure_zdotdir_in_system_zshenv
  set_zsh_as_default_shell
}

# Point the system-wide zshenv at the XDG zsh config via ZDOTDIR. Required on
# every platform (including macOS) for ~/.config/zsh/.zshrc to load at all.
# All state checks are sudo-free reads; sudo is invoked only when the setting
# is actually missing, so repeat installs never prompt for a password.
ensure_zdotdir_in_system_zshenv() {
  # Arch (and other distros shipping /etc/zsh) read /etc/zsh/zshenv; macOS/Ubuntu use /etc/zshenv
  local zshenv_path="/etc/zshenv"
  if [[ -d /etc/zsh ]] || command -v pacman &>/dev/null; then
    zshenv_path="/etc/zsh/zshenv"
  fi

  if grep -q "ZDOTDIR" "$zshenv_path" 2>/dev/null; then
    log_success "ZDOTDIR already configured in $zshenv_path"
    return 0
  fi

  local zshenv_dir
  zshenv_dir="$(dirname "$zshenv_path")"
  [[ -d "$zshenv_dir" ]] || sudo mkdir -p "$zshenv_dir"
  # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
  echo 'export ZDOTDIR="$HOME/.config/zsh"' | sudo tee -a "$zshenv_path" >/dev/null
  log_success "ZDOTDIR configured in $zshenv_path"
}

# Make zsh the default login shell. A no-op (and no sudo) when the shell is
# already zsh — which is always the case on macOS (zsh default since Catalina),
# so only bash-default platforms (Arch/Ubuntu/WSL) ever trigger the chsh.
set_zsh_as_default_shell() {
  if [[ "$SHELL" == *"zsh"* ]]; then
    log_success "Default shell is already zsh"
    return 0
  fi

  local zsh_path
  zsh_path="$(command -v zsh)"
  log_info "Changing default shell to zsh ($zsh_path)..."
  sudo chsh -s "$zsh_path" "$(whoami)"
  log_success "Default shell changed to zsh (effective after next login)"
}

usage() {
  help_header "install" "Install dotfiles and development tools"
  help_text "With no SELECTOR, every group runs."
  help_usage "$(basename "$0") --machine NAME [SELECTOR...] [OPTIONS]" \
    "$(basename "$0") --create-offline-bundle [BUNDLE OPTIONS]"

  help_section "Groups"
  help_row "system" "" "OS packages (brew/apt/pacman/flatpak/mas) — needs sudo, slowest"
  help_row "languages" "" "Language toolchains and package managers (go, rustup, uv)"
  help_row "tools" "" "Installed binaries (go, cargo, uv, npm, GitHub releases, custom)"
  help_row "config" "" "Symlink deployment and the zsh setup"
  help_row "plugins" "" "Shell, tmux, and Neovim plugins"

  help_section "Options"
  help_row "--machine" "NAME" "Machine manifest to use (required for installation)"
  help_row "--force, -f" "" "Force reinstall of all tools even if already installed"
  help_shared_options
  help_row "--offline" "" "Use offline bundle (extracts ~/installers/ from tarball)"
  help_row "--create-offline-bundle" "" "Download all installers into an offline bundle tarball"
  help_row "--help, -h" "" "Show this help message"

  help_section "Offline Bundle Options (with --create-offline-bundle)"
  help_row "--platform" "PLATFORM" "Target platform (default: linux-x86_64)"
  help_row "" "" "Supported: linux-x86_64, linux-arm64,"
  help_row "" "" "           darwin-x86_64, darwin-arm64"

  help_section "Environment Variables"
  help_row "MACHINE=name" "" "Same as --machine (flag takes precedence)"

  help_section "Examples"
  help_row "./install.sh --machine archlinux-personal-workstation"
  help_row "./install.sh --machine linux-lxc-server" "" "# minimal headless LXC / small box"
  help_row "MACHINE=archlinux-personal-workstation ./install.sh"
  help_row "./install.sh --mine" "" "# only $OWNER tools, no brew or casks"
  help_row "./install.sh go-tools" "" "# a single phase"
  help_row "./install.sh --no-system" "" "# skip the sudo-gated, slowest group"

  # Step 2 is a pick-one, which the 2a/2b numbering carries — spelling it out in
  # prose between the rows would split the section into separately sized groups
  # and stop the step comments lining up.
  help_section "Offline Workflow"
  help_row "./install.sh --create-offline-bundle" "" "# 1. Create bundle (internet machine)"
  help_row "python3 -m http.server 8000" "" "# 2a. Serve from source machine, then:"
  help_row "curl -O http://<source-ip>:8000/dotfiles-offline-*.tar.gz" "" "# 2a. Download on target (run from ~/)"
  help_row "scp dotfiles-offline-*.tar.gz user@target-host:~/" "" "# 2b. Or use scp instead"
  help_row "./install.sh --machine wsl-work-workstation --offline" "" "# 3. Install on target machine"

  help_end
  print_info "Machine manifests: install/manifests/*.yml"
  exit 0
}

extract_offline_bundle() {
  local bundle_file=""

  # Look for bundle in current directory first, then home
  for search_dir in "." "$HOME"; do
    local found
    found=$(find "$search_dir" -maxdepth 1 -name "dotfiles-offline-*.tar.gz" -type f 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
      bundle_file="$found"
      break
    fi
  done

  if [[ -z "$bundle_file" ]]; then
    log_error "No offline bundle found. Expected: dotfiles-offline-*.tar.gz in ./ or ~/"
    log_info "Create a bundle first: ./install.sh --create-offline-bundle"
    exit 1
  fi

  log_info "Found offline bundle: $bundle_file"
  log_info "Extracting to ~/installers/..."

  # Extract to home directory (tarball contains installers/ directory)
  tar -xzf "$bundle_file" -C "$HOME"

  if [[ -d "$HOME/installers" ]]; then
    log_success "Offline cache ready: ~/installers/"
    ls -la "$HOME/installers/"
  else
    log_error "Failed to extract bundle"
    exit 1
  fi
}

parse_args() {
  FORCE_INSTALL=false
  OFFLINE_MODE=false
  # --machine flag overrides MACHINE env var
  local machine_from_flag=""
  while [[ $# -gt 0 ]]; do
    consume_shared_arg "$@"
    if [[ $SHARED_ARG_CONSUMED -gt 0 ]]; then
      shift "$SHARED_ARG_CONSUMED"
      continue
    fi
    case $1 in
      --machine)
        machine_from_flag="$2"
        shift 2
        ;;
      --force | -f)
        FORCE_INSTALL=true
        shift
        ;;
      --offline)
        OFFLINE_MODE=true
        shift
        ;;
      --create-offline-bundle)
        shift
        exec bash "$DOTFILES_DIR/install/offline/create-bundle.sh" "$@"
        ;;
      --help | -h)
        usage
        ;;
      *)
        echo "Unknown option: $1"
        echo "Run with --help for usage information"
        exit 1
        ;;
    esac
  done

  # Priority: --machine flag > MACHINE env var > fail
  if [[ -n "$machine_from_flag" ]]; then
    MACHINE="$machine_from_flag"
  elif [[ -z "${MACHINE:-}" ]]; then
    echo ""
    log_error "MACHINE is required but not set"
    echo ""
    echo "Set via flag:         ./install.sh --machine <name>"
    echo "Set via environment:  export MACHINE=<name>"
    echo ""
    echo "Available manifests:"
    for f in "$DOTFILES_DIR"/install/manifests/*.yml; do
      echo "  $(basename "$f" .yml)"
    done
    exit 1
  fi

  if [[ ! -f "$DOTFILES_DIR/install/manifests/${MACHINE}.yml" ]]; then
    log_error "Machine manifest not found: install/manifests/${MACHINE}.yml"
    echo ""
    echo "Available manifests:"
    for f in "$DOTFILES_DIR"/install/manifests/*.yml; do
      echo "  $(basename "$f" .yml)"
    done
    exit 1
  fi

  export FORCE_INSTALL
  export OFFLINE_MODE
  export MACHINE

  export_selection_environment
  init_package_filters

  if [[ "$FORCE_INSTALL" == "true" ]]; then
    log_warning "Force install mode enabled - will reinstall all tools"
    echo ""
  fi

  if [[ "$OFFLINE_MODE" == "true" ]]; then
    log_info "Offline mode enabled - using cached files from ~/installers/"
    extract_offline_bundle
    echo ""
  fi
}

main() {
  local start_time

  export TITLE_COLOR="blue"
  export HEADER_COLOR="brightblue"
  export SECTION_COLOR="orange"

  # Bootstrap the YAML parser before reading the manifest. manifest_field runs
  # parse_packages.py, which imports yaml, but Apple's bundled /usr/bin/python3
  # ships without PyYAML — and the macOS install step that installs it runs only
  # AFTER the platform is known. On a fresh Mac that ordering leaves platform
  # empty and the run dies with "Unsupported platform". detect_os uses uname, so
  # it works before any Python dependency exists. The macOS phase re-checks and
  # no-ops if this already ran.
  if [[ "$(detect_os)" == "darwin" ]] && ! /usr/bin/python3 -c "import yaml" &>/dev/null; then
    log_info "Bootstrapping PyYAML for system Python (required to read manifest)..."
    /usr/bin/python3 -m pip install --user PyYAML
  fi

  PLATFORM=$(manifest_field "platform")
  start_time=$(date +%s)

  print_title "Dotfiles Installation - $MACHINE ($PLATFORM)"
  [[ "$MINE" == "true" ]] && log_info "Filtering to $OWNER tools"
  [[ "$DRY_RUN" == "true" ]] && log_info "Dry run — nothing will be modified"

  cd "$DOTFILES_DIR" || die "Could not change to dotfiles directory"

  run_selected_phases || exit 1

  [[ "$DRY_RUN" != "true" ]] && show_failures_summary

  local end_time
  end_time=$(date +%s)
  local total_duration=$((end_time - start_time))

  print_title_success "Dotfiles Installation - $MACHINE COMPLETE (${total_duration}s)"
}

# Run only when executed, never when sourced — unit tests source this file to
# call parse_args/selected_phase_names directly, exactly as update.sh allows.
#
# Deliberately not an opt-in env var: that puts the guard in the caller's hands,
# so any copy of this file lacking the check runs a full install on `source`.
# This condition needs no cooperation and cannot be defeated.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  parse_args "$@"
  main
fi
