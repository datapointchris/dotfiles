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
  local common_install="$DOTFILES_DIR/management/common/install"
  local github_releases="$common_install/github-releases"
  local custom_installers="$common_install/custom-installers"
  local lang_managers="$common_install/language-managers"
  local lang_tools="$common_install/language-tools"

  # Source run_installer wrapper
  source "$DOTFILES_DIR/management/orchestration/run-installer.sh"
  export FORCE_INSTALL=true  # Skip idempotency checks for updates

  print_section "Updating Custom Distribution Tools" $section_color
  log_info "Checking for updates to BATS, AWS CLI, Claude Code, Terraform LS..."
  run_installer "$custom_installers/bats.sh" "bats" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$custom_installers/awscli.sh" "awscli" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$custom_installers/claude-code.sh" "claude-code" 2>&1 | grep -E "Already installed|installed successfully|Verified|Skipping" || true
  run_installer "$custom_installers/terraform-ls.sh" "terraform-ls" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  log_success "Custom distribution tools checked"

  print_section "Updating GitHub Release Tools" $section_color
  log_info "Checking for updates to fzf, neovim, lazygit, yazi, etc..."
  run_installer "$github_releases/fzf.sh" "fzf" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/neovim.sh" "neovim" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/lazygit.sh" "lazygit" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/yazi.sh" "yazi" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/glow.sh" "glow" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/duf.sh" "duf" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/tflint.sh" "tflint" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/terraformer.sh" "terraformer" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/terrascan.sh" "terrascan" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/trivy.sh" "trivy" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  run_installer "$github_releases/zk.sh" "zk" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  log_success "GitHub release tools checked"

  print_section "Updating Go Toolchain" $section_color
  log_info "Checking for Go updates..."
  run_installer "$lang_managers/go.sh" "go" 2>&1 | grep -E "Already installed|installed successfully|Verified" || true
  if [[ -d "/usr/local/go/bin" ]]; then
    PATH="/usr/local/go/bin:$PATH" run_installer "$lang_tools/go-tools.sh" "go-tools" 2>&1 | grep -E "Already installed|installed successfully" || true
  fi
  log_success "Go toolchain checked"

  print_section "Rebuilding Custom Go Applications" $section_color
  if [[ -d "$DOTFILES_DIR/apps/common/sess" ]]; then
    log_info "Rebuilding sess..."
    cd "$DOTFILES_DIR/apps/common/sess" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task install
    log_success "sess rebuilt"
  fi
  if [[ -d "$DOTFILES_DIR/apps/common/toolbox" ]]; then
    log_info "Rebuilding toolbox..."
    cd "$DOTFILES_DIR/apps/common/toolbox" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task install
    log_success "toolbox rebuilt"
  fi

  unset FORCE_INSTALL  # Clean up environment variable

  print_section "Updating npm global packages via $(print_green "npm update -g")" $section_color
  if npm update -g 2>&1 | grep -v "npm warn"; then
    log_success "npm global packages updated (warnings suppressed)"
  else
    log_warning "npm global packages update failed"
  fi

  print_section "Updating Python tools via $(print_green "uv tool upgrade --all")" $section_color
  if uv tool upgrade --all; then
    log_success "Python tools updated"
  else
    log_warning "Python tools update failed"
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
