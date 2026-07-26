#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
FAILURES_LOG="/tmp/dotfiles-update-failures-$(date +%Y%m%d-%H%M%S).txt"

# Read by run-installer.sh, which is shared with install.sh — without this a
# failed `--update` run would be reported as a failed installation.
INSTALLER_ACTION="update"

export DOTFILES_DIR
export FAILURES_LOG
export INSTALLER_ACTION
export TERM=${TERM:-xterm}

# /usr/local/go/bin is the Go toolchain deploy dir — it's only added to PATH in
# .zshrc (interactive), so this non-interactive script must add it explicitly or
# `command -v go` fails in go-tools.sh (matches install.sh's go-tools invocation).
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/go/bin:/usr/local/bin:$PATH"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/run-installer.sh"

# ~/.env carries MACHINE, which selects the manifest. install.sh does the same.
if [[ -f "$HOME/.env" ]]; then
  set -a
  source "$HOME/.env"
  set +a
fi

OWNER="datapointchris"

# ================================================================
# PHASE REGISTRY
# ================================================================
# Single source of truth for --list, --dry-run, group membership, and help.
# Format: name|group|owner_aware|function
#
# owner_aware marks a phase whose contents can be traced to a GitHub owner, and
# so can be narrowed by --mine. Phases driven by a registry instead (apt, npm,
# PyPI) have no owner and are skipped under --mine rather than silently running
# in full.

UPDATE_GROUPS=(system languages tools plugins)

UPDATE_PHASES=(
  "system-packages|system|no|update_system_packages"
  "go-toolchain|languages|no|update_go_toolchain"
  "rust-toolchain|languages|no|update_rust_toolchain"
  "uv|languages|no|update_uv"
  "go-tools|tools|yes|update_go_tools"
  "cargo|tools|yes|update_cargo_packages"
  "uv-tools|tools|yes|update_uv_tools"
  "npm-globals|tools|no|update_npm_globals"
  "github-releases|tools|yes|update_github_releases"
  "custom-installers|tools|yes|update_custom_installers"
  "shell-plugins|plugins|no|update_shell_plugins"
  "tmux-plugins|plugins|no|update_tmux_plugins"
  "nvim-plugins|plugins|no|update_nvim_plugins"
)

GROUPS_SELECTED=()
GROUPS_SKIPPED=()
PACKAGE_FILTERS=()
MINE=false
DRY_RUN=false

parse_packages() {
  /usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" "$@" "${PACKAGE_FILTERS[@]}"
}

# ================================================================
# PHASES
# ================================================================
# A phase may define a companion <function>_items that echoes what it would act
# on; --dry-run prints it. Keeping it beside the phase avoids a second list to
# maintain.

update_system_packages() {
  case "$(detect_platform)" in
  macos)
    print_section "Updating Homebrew packages via $(print_green "brew update && brew upgrade")"
    if brew update && brew upgrade && brew upgrade --cask --greedy; then
      log_success "Homebrew packages updated"
    else
      log_warning "Homebrew packages update failed"
    fi

    print_section "Updating Mac App Store apps via $(print_green "mas upgrade")"
    if mas upgrade; then
      log_success "Mac App Store apps updated"
    else
      log_warning "Mac App Store apps update failed"
    fi
    ;;

  archlinux)
    print_section "Updating system packages via $(print_green "pacman -Syu")"
    if sudo pacman -Syu --noconfirm; then
      log_success "system packages updated"
    else
      log_warning "system packages update failed"
    fi

    print_section "Updating AUR packages via $(print_green "yay -Syu")"
    if yay -Syu --noconfirm; then
      log_success "AUR packages updated"
    else
      log_warning "AUR packages update failed"
    fi

    if command -v flatpak &>/dev/null; then
      print_section "Updating Flatpak apps via $(print_green "flatpak update")"
      if flatpak update -y; then
        log_success "Flatpak apps updated"
      else
        log_warning "Flatpak apps update failed"
      fi
    fi
    ;;

  wsl | linux)
    print_section "Updating system packages via $(print_green "apt update && apt upgrade")"
    if sudo apt update && sudo apt upgrade -y; then
      log_success "system packages updated"
    else
      log_warning "system packages update failed"
    fi
    ;;

  *)
    log_error "Unknown platform: $(detect_platform)"
    return 1
    ;;
  esac
}

update_go_toolchain() {
  print_section "Updating Go toolchain via $(print_green "go.sh --update")"
  if bash "$DOTFILES_DIR/install/common/language-managers/go.sh" --update; then
    log_success "Go updated"
  else
    log_warning "Go update failed"
  fi
}

update_rust_toolchain() {
  print_section "Updating Rust toolchain via $(print_green "rustup update")"
  if rustup update; then
    log_success "Rust toolchain updated"
  else
    log_warning "Rust toolchain update failed"
  fi
}

update_uv() {
  print_section "Updating uv package manager via $(print_green "uv self update")"
  if uv self update; then
    log_success "uv updated"
  else
    log_warning "uv update failed"
  fi
}

update_go_tools() {
  print_section "Updating Go tools via $(print_green "go-tools.sh --update")"
  if bash "$DOTFILES_DIR/install/common/language-tools/go-tools.sh" --update; then
    log_success "Go tools updated"
  else
    log_warning "Go tools update failed"
  fi
}

update_go_tools_items() {
  parse_packages --type=go --format=name_package | cut -d'|' -f1
}

update_cargo_packages() {
  print_section "Updating Rust packages via $(print_green "cargo binstall")"
  local cargo_failures=0
  while IFS='|' read -r package binary_name; do
    [[ -z "$package" ]] && continue
    if cargo binstall -y "$package" 2>&1 | grep -q "already installed"; then
      log_success "$package already up-to-date"
    elif command -v "$binary_name" >/dev/null 2>&1; then
      log_success "$package updated"
    else
      log_warning "$package update failed"
      cargo_failures=$((cargo_failures + 1))
    fi
  done < <(parse_packages --type=cargo --format=name_command)

  if [[ $cargo_failures -eq 0 ]]; then
    log_success "Rust packages updated"
  else
    log_warning "$cargo_failures Rust package(s) failed to update"
  fi
}

update_cargo_packages_items() {
  parse_packages --type=cargo --format=name_command | cut -d'|' -f1
}

update_uv_tools() {
  # `uv tool upgrade --all` cannot be narrowed, so --mine upgrades the owned
  # tools by name instead.
  if [[ "$MINE" == "true" ]]; then
    print_section "Updating Python tools via $(print_green "uv tool upgrade <tool>")"
    local tool
    while IFS=: read -r tool _; do
      [[ -z "$tool" ]] && continue
      if uv tool upgrade "$tool"; then
        log_success "$tool updated"
      else
        log_warning "$tool update failed"
      fi
    done < <(parse_packages --type=git_uv)
    return 0
  fi

  print_section "Updating Python tools via $(print_green "uv tool upgrade --all")"
  if uv tool upgrade --all; then
    log_success "Python tools updated"
  else
    log_warning "Python tools update failed"
  fi
}

update_uv_tools_items() {
  parse_packages --type=git_uv | cut -d: -f1
}

update_npm_globals() {
  print_section "Updating npm global packages via $(print_green "npm update -g")"
  npm update -g 2>&1 | grep -v "npm warn" || true
  if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
    log_success "npm global packages updated"
  else
    log_warning "npm global packages update failed"
  fi
}

update_github_releases() {
  print_section "Updating GitHub Release Tools"
  local github_releases="$DOTFILES_DIR/install/common/github-releases"
  local tool script
  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    script="$github_releases/${tool}.sh"
    if [[ ! -f "$script" ]]; then
      log_warning "No installer script for github release: $tool (packages verify should have caught this)"
      continue
    fi
    run_installer "$script" "$tool" --update
  done < <(parse_packages --type=github)
}

update_github_releases_items() {
  parse_packages --type=github
}

update_custom_installers() {
  print_section "Updating Custom Distribution Tools"
  local custom_installers="$DOTFILES_DIR/install/common/custom-installers"
  local tool script
  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    script="$custom_installers/${tool}.sh"
    if [[ ! -f "$script" ]]; then
      log_warning "No installer script for custom installer: $tool (packages verify should have caught this)"
      continue
    fi
    run_installer "$script" "$tool" --update
  done < <(parse_packages --type=custom)
}

update_custom_installers_items() {
  parse_packages --type=custom
}

update_shell_plugins() {
  print_section "Updating Shell plugins via $(print_green "git pull")"
  local name plugin_dir branch
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    plugin_dir="$HOME/.config/zsh/plugins/$name"
    [[ ! -d "$plugin_dir" ]] && continue

    branch=$(git -C "$plugin_dir" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [[ -z "$branch" ]] && branch=$(git -C "$plugin_dir" remote show origin | grep 'HEAD branch' | cut -d' ' -f5)

    if git -C "$plugin_dir" pull origin "$branch" --quiet; then
      log_success "$name updated"
    else
      log_error "$name update failed"
    fi
  done < <(parse_packages --type=shell-plugins --format=names)
}

update_shell_plugins_items() {
  parse_packages --type=shell-plugins --format=names
}

update_tmux_plugins() {
  print_section "Updating tmux plugins via $(print_green "tpm/bin/update_plugins")"
  if "$HOME/.config/tmux/plugins/tpm/bin/update_plugins" all; then
    log_success "tmux plugins updated"
  else
    log_warning "tmux plugins update failed"
  fi
}

update_nvim_plugins() {
  print_section "Updating Neovim plugins via $(print_green ":Lazy update")"
  local nvim_output
  nvim_output=$(mktemp)
  if nvim --headless "+Lazy! update" +qa &>"$nvim_output"; then
    log_success "Neovim plugins updated"
    [[ "${DEBUG:-}" == "true" ]] && cat "$nvim_output"
  else
    log_warning "Neovim plugins update failed"
    log_warning "Full output:"
    cat "$nvim_output"
  fi
  rm -f "$nvim_output"
}

# ================================================================
# SELECTION
# ================================================================

group_is_valid() {
  local candidate="$1" group
  for group in "${UPDATE_GROUPS[@]}"; do
    [[ "$group" == "$candidate" ]] && return 0
  done
  return 1
}

array_contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

phase_selected() {
  local group="$1" owner_aware="$2"

  if [[ ${#GROUPS_SELECTED[@]} -gt 0 ]] && ! array_contains "$group" "${GROUPS_SELECTED[@]}"; then
    return 1
  fi
  if [[ ${#GROUPS_SKIPPED[@]} -gt 0 ]] && array_contains "$group" "${GROUPS_SKIPPED[@]}"; then
    return 1
  fi
  if [[ "$MINE" == "true" && "$owner_aware" != "yes" ]]; then
    return 1
  fi
  return 0
}

# Names of the phases the current selection resolves to, in registry order.
# main() and the unit tests both read the selection through this, so there is no
# second implementation to disagree with.
selected_phase_names() {
  local entry name group owner_aware
  for entry in "${UPDATE_PHASES[@]}"; do
    IFS='|' read -r name group owner_aware _ <<<"$entry"
    phase_selected "$group" "$owner_aware" && echo "$name"
  done
  return 0
}

run_phase() {
  local name="$1" group="$2" fn="$3"

  if [[ "$DRY_RUN" != "true" ]]; then
    "$fn"
    return $?
  fi

  print_section "$name ($group)"
  if declare -F "${fn}_items" >/dev/null; then
    local items item
    items=$("${fn}_items")
    if [[ -n "$items" ]]; then
      while IFS= read -r item; do
        echo "  $item"
      done <<<"$items"
    else
      log_warning "  nothing selected"
    fi
  fi
}

list_phases() {
  local group entry name phase_group owner_aware
  print_title "Update Groups"
  for group in "${UPDATE_GROUPS[@]}"; do
    print_section "$group"
    for entry in "${UPDATE_PHASES[@]}"; do
      IFS='|' read -r name phase_group owner_aware _ <<<"$entry"
      [[ "$phase_group" != "$group" ]] && continue
      if [[ "$owner_aware" == "yes" ]]; then
        echo "  $name  (supports --mine)"
      else
        echo "  $name"
      fi
    done
  done
  exit 0
}

# ================================================================
# ARGUMENTS
# ================================================================

usage() {
  echo "Usage: $(basename "$0") [GROUP...] [OPTIONS]"
  echo ""
  echo "Update system packages, language tools, and plugins."
  echo "With no GROUP, every group runs."
  echo ""
  echo "Groups:"
  echo "  system       OS packages (brew/apt/pacman/yay/flatpak/mas) — needs sudo, slowest"
  echo "  languages    Language toolchains and package managers (go, rustup, uv)"
  echo "  tools        Installed binaries (go, cargo, uv, npm, GitHub releases, custom)"
  echo "  plugins      Shell, tmux, and Neovim plugins"
  echo ""
  echo "Options:"
  echo "  --skip GROUP   Skip a group (repeatable)"
  echo "  --no-system    Alias for --skip system"
  echo "  --mine         Only tools owned by $OWNER; groups without an owner are skipped"
  echo "  --list         Show every group and its phases"
  echo "  --dry-run      Show what would run without running it"
  echo "  --help, -h     Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./update.sh                       # everything"
  echo "  ./update.sh tools                 # only installed binaries"
  echo "  ./update.sh tools plugins         # two groups"
  echo "  ./update.sh --no-system           # skip the sudo-gated, slowest group"
  echo "  ./update.sh --mine                # refresh only $OWNER tools"
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
    --skip)
      if [[ -z "${2:-}" ]]; then
        log_error "--skip requires a group name"
        exit 1
      fi
      if ! group_is_valid "$2"; then
        log_error "Unknown group: $2"
        echo "Valid groups: ${UPDATE_GROUPS[*]}"
        exit 1
      fi
      GROUPS_SKIPPED+=("$2")
      shift 2
      ;;
    --no-system)
      GROUPS_SKIPPED+=("system")
      shift
      ;;
    --mine)
      MINE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --list)
      list_phases
      ;;
    --help | -h)
      usage
      ;;
    -*)
      log_error "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
    *)
      if ! group_is_valid "$1"; then
        log_error "Unknown group: $1"
        echo "Valid groups: ${UPDATE_GROUPS[*]}"
        exit 1
      fi
      GROUPS_SELECTED+=("$1")
      shift
      ;;
    esac
  done

  if [[ -n "${MACHINE:-}" ]]; then
    if [[ -f "$DOTFILES_DIR/install/manifests/${MACHINE}.yml" ]]; then
      PACKAGE_FILTERS+=(--manifest="$MACHINE")
    else
      log_warning "Manifest not found for MACHINE=$MACHINE — updating every package in packages.yml"
    fi
  fi

  if [[ "$MINE" == "true" ]]; then
    PACKAGE_FILTERS+=(--owner="$OWNER")
    # go-tools.sh reads this to narrow its own packages.yml query
    export PACKAGE_OWNER="$OWNER"
  fi
}

# ================================================================

main() {
  parse_args "$@"

  local platform start_time end_time total_duration
  platform=$(detect_platform)
  start_time=$(date +%s)

  export TITLE_COLOR="blue"
  export SECTION_COLOR="yellow"

  print_title "System Update - $platform"
  [[ "$MINE" == "true" ]] && log_info "Filtering to $OWNER tools"
  [[ "$DRY_RUN" == "true" ]] && log_info "Dry run — nothing will be modified"

  local entry name group owner_aware fn ran=0
  for entry in "${UPDATE_PHASES[@]}"; do
    IFS='|' read -r name group owner_aware fn <<<"$entry"
    phase_selected "$group" "$owner_aware" || continue
    run_phase "$name" "$group" "$fn"
    ran=$((ran + 1))
  done

  if [[ $ran -eq 0 ]]; then
    log_warning "No phases selected"
    exit 1
  fi

  [[ "$DRY_RUN" != "true" ]] && show_failures_summary

  end_time=$(date +%s)
  total_duration=$((end_time - start_time))

  print_title_success "System Update - $platform COMPLETE (${total_duration}s)"
}

# Run only when executed, never when sourced — unit tests source this file to
# call parse_args/selected_phase_names directly.
#
# Deliberately not an opt-in env var: that puts the guard in the caller's hands,
# so any copy of this file lacking the check runs a full system update on
# `source`. This condition needs no cooperation and cannot be defeated.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
