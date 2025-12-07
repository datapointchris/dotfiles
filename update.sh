#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"

update_shell_plugins() {
  local plugins
  plugins=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --type=shell-plugins --format=names)

  for name in $plugins; do
    local plugin_dir="$HOME/.config/shell/plugins/$name"
    [[ ! -d "$plugin_dir" ]] && continue

    cd "$plugin_dir" || continue

    local branch
    branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [[ -z "$branch" ]] && branch=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)

    if git pull origin "$branch" --quiet; then
      log_success "$name updated"
    else
      log_error "$name update failed"
    fi
  done
}

update_common_tools() {
  print_section "Updating npm global packages via $(print_green "npm update -g")" $section_color
  if npm update -g 2>&1 | grep -v "npm warn"; then
    log_success "npm global packages updated (warnings suppressed)"
  else
    log_warning "npm global packages update failed"
  fi

  print_section "Updating uv package manager via $(print_green "uv self update")" $section_color
  if uv self update; then
    log_success "uv updated"
  else
    log_warning "uv update failed"
  fi

  print_section "Updating Python tools via $(print_green "uv tool upgrade --all")" $section_color
  if uv tool upgrade --all; then
    log_success "Python tools updated"
  else
    log_warning "Python tools update failed"
  fi

  print_section "Updating Rust toolchain via $(print_green "rustup update")" $section_color
  if rustup update; then
    log_success "Rust toolchain updated"
  else
    log_warning "Rust toolchain update failed"
  fi

  print_section "Updating Rust packages via $(print_green "cargo install-update -a")" $section_color
  if cargo install-update -a; then
    log_success "Rust packages updated"
  else
    log_warning "Rust packages update failed"
  fi

  log_info "Updating Shell plugins via $(print_green "git pull")"
  if update_shell_plugins; then
    log_success "Shell plugins updated"
  else
    log_warning "Shell plugins update failed"
  fi

  print_section "Updating tmux plugins via $(print_green "tpm/bin/update_plugins")" $section_color
  if "$HOME/.config/tmux/plugins/tpm/bin/update_plugins" all; then
    log_success "tmux plugins updated"
  else
    log_warning "tmux plugins update failed"
  fi

  print_section "Updating Neovim plugins via $(print_green ":Lazy update")" $section_color
  if nvim --headless +Lazy! update +qa 2>&1; then
    log_success "Neovim plugins updated"
  else
    log_warning "Neovim plugins update failed"
  fi
}

main() {
  local platform start_time end_time total_duration title_color section_color
  platform=$(detect_platform)
  start_time=$(date +%s)
  title_color="blue"
  section_color="yellow"

  print_title "System Update - $platform" $title_color

  case "$platform" in
    macos)
      print_section "Updating Homebrew packages via $(print_green "brew update && brew upgrade")" $section_color
      if brew update && brew upgrade && brew upgrade --cask --greedy; then
        log_success "Homebrew packages updated"
      else
        log_warning "Homebrew packages update failed"
      fi

      print_section "Updating Mac App Store apps via $(print_green "mas upgrade")" $section_color
      if mas upgrade; then
        log_success "Mac App Store apps updated"
      else
        log_warning "Mac App Store apps update failed"
      fi

      update_common_tools
      ;;

    wsl)
      print_section "Updating system packages via $(print_green "apt update && apt upgrade")" $section_color
      if sudo apt update && sudo apt upgrade -y; then
        log_success "system packages updated"
      else
        log_warning "system packages update failed"
      fi

      update_common_tools
      ;;

    arch)
      print_section "Updating system packages via $(print_green "pacman -Syu")" $section_color
      if sudo pacman -Syu --noconfirm; then
        log_success "system packages updated"
      else
        log_warning "system packages update failed"
      fi

      print_section "Updating AUR packages via $(print_green "yay -Syu")" $section_color
      if yay -Syu --noconfirm; then
        log_success "AUR packages updated"
      else
        log_warning "AUR packages update failed"
      fi

      update_common_tools
      ;;

    *)
      log_error "Unknown platform: $platform"
      exit 1
      ;;
  esac
  local end_time
  end_time=$(date +%s)
  local total_duration=$((end_time - start_time))

  print_title_success "System Update - $platform COMPLETE (${total_duration}s)"
}

main
