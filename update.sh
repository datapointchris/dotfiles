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
  plugins=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" \
    --type=shell-plugins --format=names)

  for name in $plugins; do
    local plugin_dir="$HOME/.config/zsh/plugins/$name"
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
  print_section "Updating Go toolchain via $(print_green "go.sh --update")"
  if bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh" --update; then
    log_success "Go updated"
  else
    log_warning "Go update failed"
  fi

  print_section "Updating Rust toolchain via $(print_green "rustup update")"
  if rustup update; then
    log_success "Rust toolchain updated"
  else
    log_warning "Rust toolchain update failed"
  fi

  print_section "Updating Rust packages via $(print_green "cargo install-update -a")"
  if cargo install-update -a; then
    log_success "Rust packages updated"
  else
    log_warning "Rust packages update failed"
  fi

  print_section "Updating uv package manager via $(print_green "uv self update")"
  if uv self update; then
    log_success "uv updated"
  else
    log_warning "uv update failed"
  fi

  print_section "Updating Python tools via $(print_green "uv tool upgrade --all")"
  if uv tool upgrade --all; then
    log_success "Python tools updated"
  else
    log_warning "Python tools update failed"
  fi

  print_section "Updating nvm and Node.js via $(print_green "nvm.sh --update")"
  if bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update; then
    log_success "nvm and Node.js updated"
  else
    log_warning "nvm and Node.js update failed"
  fi

  print_section "Updating npm global packages via $(print_green "npm update -g")"
  if npm update -g 2>&1 | grep -v "npm warn"; then
    log_success "npm global packages updated (warnings suppressed)"
  else
    log_warning "npm global packages update failed"
  fi

  print_section "Updating tenv and Terraform via $(print_green "tenv.sh --update")"
  if bash "$DOTFILES_DIR/management/common/install/github-releases/tenv.sh" --update; then
    log_success "tenv and Terraform updated"
  else
    log_warning "tenv and Terraform update failed"
  fi

  print_section "Updating Shell plugins via $(print_green "git pull")"
  if update_shell_plugins; then
    log_success "Shell plugins updated"
  else
    log_warning "Shell plugins update failed"
  fi

  print_section "Updating tmux plugins via $(print_green "tpm/bin/update_plugins")"
  if "$HOME/.config/tmux/plugins/tpm/bin/update_plugins" all; then
    log_success "tmux plugins updated"
  else
    log_warning "tmux plugins update failed"
  fi

  print_section "Updating Neovim plugins via $(print_green ":Lazy update")"
  if nvim --headless +Lazy! update +qa 2>&1; then
    log_success "Neovim plugins updated"
  else
    log_warning "Neovim plugins update failed"
  fi
}

main() {
  local platform start_time end_time total_duration
  platform=$(detect_platform)
  start_time=$(date +%s)

  export TITLE_COLOR="blue"
  export SECTION_COLOR="yellow"

  print_title "System Update - $platform"

  case "$platform" in
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

      update_common_tools
      ;;

    wsl)
      print_section "Updating system packages via $(print_green "apt update && apt upgrade")"
      if sudo apt update && sudo apt upgrade -y; then
        log_success "system packages updated"
      else
        log_warning "system packages update failed"
      fi

      update_common_tools
      ;;

    arch)
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
