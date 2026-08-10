#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
FAILURES_LOG="/tmp/dotfiles-update-failures-$(date +%Y%m%d-%H%M%S).txt"
MISSING_LOG="/tmp/dotfiles-update-missing-$(date +%Y%m%d-%H%M%S).txt"

# Read by run-installer.sh, which is shared with install.sh — without this a
# failed `--update` run would be reported as a failed installation. The release
# installers also read it to decide that an absent binary is a thing to report
# rather than a thing to install.
INSTALLER_ACTION="update"

export DOTFILES_DIR
export FAILURES_LOG
export MISSING_LOG
export INSTALLER_ACTION
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/install/tool-path.sh"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/run-installer.sh"
source "$DOTFILES_DIR/install/common/lib/installed-versions.sh"
source "$DOTFILES_DIR/install/common/lib/uv-git-tools.sh"
source "$DOTFILES_DIR/install/common/lib/package-query.sh"
source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"

# ~/.env carries MACHINE, which selects the manifest. install.sh does the same.
if [[ -f "$HOME/.env" ]]; then
  set -a
  source "$HOME/.env"
  set +a
fi

source "$DOTFILES_DIR/install/phases.sh"

# ================================================================
# REPORTING
# ================================================================

# Reports what moved between two sorted "<name> <version>" snapshots, for the
# phases whose update command updates many things at once and says nothing
# useful about which. Prints up_to_date_message when nothing moved.
#
# Additions and removals are reported as such rather than folded into "updated":
# a plugin that appears because the config gained it, or disappears because the
# config dropped it, is not an upgrade and reading as one hides the real change.
report_snapshot_changes() {
  local before="$1" after="$2" up_to_date_message="$3"
  local changed=false name version previous

  while read -r name version; do
    [[ -z "$name" ]] && continue
    changed=true
    previous=$(awk -v tracked="$name" '$1 == tracked { print $2 }' <<<"$before")
    if [[ -z "$previous" ]]; then
      log_success "$name installed ($version)"
    else
      log_success "$name updated: $previous → $version"
    fi
  done < <(comm -13 <(sort <<<"$before") <(sort <<<"$after"))

  while read -r name; do
    [[ -z "$name" ]] && continue
    changed=true
    log_success "$name removed"
  done < <(comm -23 <(awk '{print $1}' <<<"$before" | sort) <(awk '{print $1}' <<<"$after" | sort))

  [[ "$changed" == "true" ]] || log_success "$up_to_date_message"
  return 0
}

# ================================================================
# PHASES
# ================================================================
# What each phase would act on is resolved by the items_<phase> functions in
# install/phases.sh, which --dry-run prints and install shares.
#
# No phase installs a tool it finds missing. Three of them used to, purely
# because `go install @latest`, `cargo binstall`, and the release installers are
# install-or-upgrade commands while `uv tool upgrade` and `<tool> update` are
# not — so whether update created a tool came down to which section of
# packages.yml it had been added to. Missing tools are recorded and reported at
# the end instead.

update_system_packages() {
  case "$(detect_platform)" in
    macos)
      print_section "Updating Homebrew packages via $(print_green "brew update && brew upgrade")"
      if brew update && brew upgrade && brew upgrade --cask --greedy; then
        log_success "Homebrew update completed"
      else
        log_warning "Homebrew packages update failed"
      fi

      print_section "Updating Mac App Store apps via $(print_green "mas upgrade")"
      if mas upgrade; then
        log_success "Mac App Store update completed"
      else
        log_warning "Mac App Store apps update failed"
      fi
      ;;

    archlinux)
      print_section "Updating system packages via $(print_green "pacman -Syu")"
      if sudo pacman -Syu --noconfirm; then
        log_success "system package update completed"
      else
        log_warning "system packages update failed"
      fi

      print_section "Updating AUR packages via $(print_green "yay -Syu")"
      if yay -Syu --noconfirm; then
        log_success "AUR update completed"
      else
        log_warning "AUR packages update failed"
      fi

      if command -v flatpak &>/dev/null; then
        print_section "Updating Flatpak apps via $(print_green "flatpak update")"
        if flatpak update -y; then
          log_success "Flatpak update completed"
        else
          log_warning "Flatpak apps update failed"
        fi
      fi
      ;;

    wsl | linux)
      print_section "Updating system packages via $(print_green "apt update && apt upgrade")"
      if sudo apt update && sudo apt upgrade -y; then
        log_success "system package update completed"
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

# The CLI addresses the runtimes as one resource, so each of these converges all
# of them and whichever runs second finds nothing to do. The rows here stay one
# per runtime because `apply.REGISTRY` does, and both go in step C.
#
# What changed with them: a runtime is installed when it is missing or below the
# floor its `runtimes` row declares, rather than on every update run. Go above its
# floor is what `check` has always called converged, and the two answers agree now
# instead of one upgrading what the other called fine.
converge_toolchains() {
  dotfiles_python -m dotfiles.main toolchains apply
}

update_go_toolchain() {
  print_section "Updating Go toolchain via $(print_green "dotfiles toolchains apply")"
  if converge_toolchains; then
    log_success "Go toolchain update completed"
  else
    log_warning "Go update failed"
  fi
}

update_node_toolchain() {
  print_section "Updating Node default via $(print_green "dotfiles toolchains apply")"
  if converge_toolchains; then
    log_success "Node toolchain update completed"
  else
    log_warning "Node update failed"
  fi
}

update_rust_toolchain() {
  print_section "Updating Rust toolchain via $(print_green "rustup update")"
  if rustup update; then
    log_success "Rust toolchain update completed"
  else
    log_warning "Rust toolchain update failed"
  fi
}

update_uv() {
  print_section "Updating uv package manager via $(print_green "uv self update")"
  if uv self update; then
    log_success "uv update completed"
  else
    log_warning "uv update failed"
  fi
}

update_go_tools() {
  print_section "Updating Go tools via $(print_green "dotfiles packages apply --source go_tools")"
  if converge_section go_tools; then
    log_success "Go tools update completed"
  else
    log_warning "Go tools update failed"
  fi
}

update_cargo_packages() {
  print_section "Updating Rust packages via $(print_green "dotfiles packages apply --source cargo_packages")"
  if converge_section cargo_packages; then
    log_success "Rust packages update completed"
  else
    log_warning "Rust packages update failed"
  fi
}

upgrade_uv_tool() {
  local tool="$1"
  local before after upgrade_output upgrade_status=0

  if ! uv_tool_is_installed "$tool"; then
    log_warning "$tool not installed — skipping update"
    record_missing_tool "$tool" "uv-tools"
    return 0
  fi

  before=$(uv_tool_installed_ref "$tool") || before=""

  upgrade_output=$(uv tool upgrade "$tool" 2>&1) || upgrade_status=$?
  [[ "${DEBUG:-}" == "true" ]] && echo "$upgrade_output"

  if [[ $upgrade_status -ne 0 ]]; then
    log_warning "$tool update failed"
    echo "$upgrade_output" >&2
    return 1
  fi

  after=$(uv_tool_installed_ref "$tool") || after=""

  if [[ -z "$after" ]]; then
    log_success "$tool updated (version unknown)"
  elif [[ -z "$before" ]]; then
    log_success "$tool installed ($after)"
  elif [[ "$before" == "$after" ]]; then
    log_success "$tool already at latest ($after)"
  else
    log_success "$tool updated: $before → $after"
  fi
}

# Moves a release-tracking git tool's pin to the newest release.
#
# `uv tool upgrade` cannot do this: it re-resolves the requirement it finds, and
# a pinned tag resolves to the same commit every time, so it exits 0 having done
# nothing — which is how syncer reported "already at latest" eight releases
# behind. Reinstalling the requirement is the only thing that moves a pin.
#
# An install with no pin is reinstalled even when its version already matches
# the newest release, because the pin is also what enables the tool's own update
# notice. That converts the tools installed before this was the install shape.
upgrade_released_uv_tool() {
  local tool="$1" repo="$2" before="$3"
  local latest pinned install_output install_status=0

  # `uv tool install --force` below would create the tool outright, so absence
  # has to be caught here rather than left to uv to report.
  if ! uv_tool_is_installed "$tool"; then
    log_warning "$tool not installed — skipping update"
    record_missing_tool "$tool" "uv-tools"
    return 0
  fi

  if ! latest=$(uv_git_tool_latest_ref "$repo"); then
    log_warning "$tool: failed to resolve the latest release of $repo"
    return 1
  fi

  pinned=$(uv_tool_pinned_rev "$tool") || pinned=""
  if [[ -n "$pinned" ]]; then
    version_compare "$pinned" "$latest"
    # 0 equal, 2 pinned ahead of the newest release — a prerelease build, so
    # leave it rather than reinstalling backwards over it.
    case $? in
      0 | 2)
        log_success "$tool already at latest (${before:-$pinned})"
        return 0
        ;;
    esac
  fi

  install_output=$(uv tool install --force --quiet "$(uv_git_tool_requirement "$tool" "$repo" "$latest")" 2>&1) \
    || install_status=$?
  [[ "${DEBUG:-}" == "true" ]] && echo "$install_output"

  if [[ $install_status -ne 0 ]]; then
    log_warning "$tool update to $latest failed"
    echo "$install_output" >&2
    return 1
  fi

  local after
  after=$(uv_tool_installed_ref "$tool") || after="$latest"
  if [[ "$before" == "$after" ]]; then
    log_success "$tool already at latest ($after, now pinned to $latest)"
  else
    log_success "$tool updated: ${before:-none} → $after"
  fi
}

update_uv_tools() {
  # By name rather than `uv tool upgrade --all`: --all cannot be narrowed for
  # --mine, and its exit code is 0 whether or not anything changed, so a
  # per-tool before/after ref is the only way to report the truth. Under --mine
  # the index-installed tools have no owner and come back empty.
  print_section "Updating Python tools via $(print_green "uv tool upgrade <tool>")"
  local tool count=0
  while IFS= read -r tool; do
    [[ -z "$tool" ]] && continue
    count=$((count + 1))
    upgrade_uv_tool "$tool"
  done < <(parse_packages --type=uv)

  # The git tools carry their repo and ref mode, because moving a pin means
  # reinstalling the requirement rather than upgrading the tool.
  local name repo ref_mode before
  while IFS='|' read -r name repo ref_mode; do
    [[ -z "$name" ]] && continue
    count=$((count + 1))
    if [[ "$ref_mode" == "release" ]]; then
      before=$(uv_tool_installed_ref "$name") || before=""
      upgrade_released_uv_tool "$name" "$repo" "$before"
    else
      upgrade_uv_tool "$name"
    fi
  done < <(parse_packages --type=git_uv)

  [[ $count -eq 0 ]] && log_info "no Python tools selected"
  return 0
}

update_npm_globals() {
  print_section "Updating npm global packages via $(print_green "npm update -g")"

  local before after npm_output npm_status=0
  before=$(npm_global_versions) || before=""

  # Captured rather than piped: reading PIPESTATUS after `|| true` reported the
  # status of `true`, so every failure was logged as a success.
  npm_output=$(npm update -g 2>&1) || npm_status=$?
  grep -v "npm warn" <<<"$npm_output" || true

  if [[ $npm_status -ne 0 ]]; then
    log_warning "npm global packages update failed"
    return 1
  fi

  after=$(npm_global_versions) || after=""

  if [[ -z "$before" || -z "$after" ]]; then
    log_success "npm global packages update completed (versions unavailable)"
    return 0
  fi

  report_snapshot_changes "$before" "$after" "npm global packages already at latest"
}

# The two phases with no bash left to run. `apply` converges rather than installing
# only what is absent, so narrowing it to one section is the whole of what the
# per-tool loops here used to do — and it is the shape the rest of this file takes
# as each phase converts.
#
# --owner rather than PACKAGE_OWNER: the bash tool scripts read that variable out
# of the environment, but a phase that runs the CLI has to be told, and a phase
# selected by --mine that then updates every tool is worse than one that was
# never selected.
converge_section() {
  local section="$1"
  dotfiles_python -m dotfiles.main packages apply --source "$section" ${PACKAGE_OWNER:+--owner "$PACKAGE_OWNER"}
}

update_github_releases() {
  print_section "Updating GitHub Release Tools"
  converge_section github_releases
}

update_custom_installers() {
  print_section "Updating Custom Distribution Tools"
  converge_section custom_installers
}

update_shell_plugins() {
  print_section "Updating Shell plugins via $(print_green "git pull")"
  local name plugin_dir branch before after
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    plugin_dir="$HOME/.config/zsh/plugins/$name"
    [[ ! -d "$plugin_dir" ]] && continue

    branch=$(git -C "$plugin_dir" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [[ -z "$branch" ]] && branch=$(git -C "$plugin_dir" remote show origin | grep 'HEAD branch' | cut -d' ' -f5)

    # `git pull --quiet` on a current clone exits 0 and prints nothing, so the
    # commit is what distinguishes a real update from a no-op.
    before=$(git_checkout_commit "$plugin_dir") || before=""

    if ! git -C "$plugin_dir" pull origin "$branch" --quiet; then
      log_error "$name update failed"
      continue
    fi

    after=$(git_checkout_commit "$plugin_dir") || after=""
    if [[ "$before" == "$after" ]]; then
      log_success "$name already at latest ($after)"
    else
      log_success "$name updated: $before → $after"
    fi
  done < <(parse_packages --type=shell-plugins --format=names)
}

update_tmux_plugins() {
  print_section "Updating tmux plugins via $(print_green "tpm/bin/update_plugins")"
  local plugins_dir="$HOME/.config/tmux/plugins"
  local before after tpm_output tpm_status=0

  # tpm exits 0 and prints the same "Done, thanks" whether or not a plugin moved,
  # so the per-plugin commits are the only evidence of what it actually did.
  before=$(git_checkouts_snapshot "$plugins_dir") || before=""

  tpm_output=$("$plugins_dir/tpm/bin/update_plugins" all 2>&1) || tpm_status=$?
  [[ "${DEBUG:-}" == "true" ]] && echo "$tpm_output"

  if [[ $tpm_status -ne 0 ]]; then
    log_warning "tmux plugins update failed"
    echo "$tpm_output" >&2
    return 1
  fi

  after=$(git_checkouts_snapshot "$plugins_dir") || after=""
  report_snapshot_changes "$before" "$after" "tmux plugins already at latest"
}

update_nvim_plugins() {
  print_section "Updating Neovim plugins via $(print_green ":Lazy update")"
  local plugins_dir="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/lazy"
  local before after nvim_output nvim_status=0

  # `:Lazy! update` exits 0 for a no-op and its output is a rendered TUI frame,
  # so the per-plugin commits are what say which plugins moved.
  #
  # The checkouts rather than lazy-lock.json: the lockfile only moves when
  # upstream does, so a plugin dragged back to its pinned commit — the repair
  # case — leaves it untouched and would read as nothing having happened.
  before=$(git_checkouts_snapshot "$plugins_dir") || before=""

  nvim_output=$(nvim --headless "+Lazy! update" +qa 2>&1) || nvim_status=$?
  [[ "${DEBUG:-}" == "true" ]] && echo "$nvim_output"

  if [[ $nvim_status -ne 0 ]]; then
    log_warning "Neovim plugins update failed"
    echo "$nvim_output" >&2
    return 1
  fi

  after=$(git_checkouts_snapshot "$plugins_dir") || after=""
  report_snapshot_changes "$before" "$after" "Neovim plugins already at latest"
}

# ================================================================
# ARGUMENTS
# ================================================================

usage() {
  help_header "update" "Update system packages, language tools, and plugins."
  help_text "With no SELECTOR, every group runs. Update never installs a tool that"
  help_text "is missing — it reports it and leaves it to \`dotfiles apply\`."
  help_usage "$(basename "$0") [SELECTOR...] [OPTIONS]"

  help_section "Groups"
  help_row "system" "" "OS packages (brew/apt/pacman/yay/flatpak/mas) — needs sudo, slowest"
  help_row "languages" "" "Language toolchains and package managers (go, rustup, uv)"
  help_row "tools" "" "Installed binaries (go, cargo, uv, npm, GitHub releases, custom)"
  help_row "plugins" "" "Shell, tmux, and Neovim plugins"

  help_section "Options"
  help_shared_options
  help_row "--help, -h" "" "Show this help message"

  help_section "Examples"
  help_row "./update.sh" "" "# everything"
  help_row "./update.sh tools" "" "# only installed binaries"
  help_row "./update.sh go-tools" "" "# a single phase"
  help_row "./update.sh tools plugins" "" "# two groups"
  help_row "./update.sh --no-system" "" "# skip the sudo-gated, slowest group"
  help_row "./update.sh --mine" "" "# refresh only $OWNER tools"

  help_end
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    consume_shared_arg "$@"
    if [[ $SHARED_ARG_CONSUMED -gt 0 ]]; then
      shift "$SHARED_ARG_CONSUMED"
      continue
    fi
    case $1 in
      --help | -h)
        usage
        ;;
      *)
        log_error "Unknown option: $1"
        echo "Run with --help for usage information"
        exit 1
        ;;
    esac
  done

  export_selection_environment
  init_package_filters
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

  run_selected_phases || exit 1

  if [[ "$DRY_RUN" != "true" ]]; then
    show_failures_summary
    show_missing_summary
  fi

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
