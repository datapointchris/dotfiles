#!/usr/bin/env bash
# ================================================================
# Installation Verification Script
# ================================================================
# Verifies that all tools and configurations are properly installed
# Should be run in a FRESH shell (not during installation)
# This ensures environment variables and PATH are loaded correctly
# ================================================================

set -euo pipefail

# Source logging library (runs after installation, can use $HOME/dotfiles)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/python.sh"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
REFUSED_CHECKS=0

# Arrays to track failures
declare -a FAILED_TOOLS=()
declare -a REFUSED_TOOLS=()

# ================================================================
# What the last apply refused
# ================================================================
# A refusal is an *explained* absence: the run reached the item, wrote nothing,
# and said why. An offline machine has no go.dev to fetch a toolchain from and no
# rustup.rs to run, because its bundle stages the Go and Rust tools prebuilt
# instead — so it converges with four items refused, and `Result.refused` is how
# the providers say so. Counting those as failures reported seven broken tools on
# a machine that was working exactly as designed, which is the same disease as a
# false red anywhere else: an unreadable verdict is one nobody acts on.
#
# Read from this machine's own newest apply rather than from a list here, so it
# cannot disagree with what the install actually did, and so an installer that
# stops refusing something starts requiring it with nothing here to update.
#
# Every way of failing to read one leaves the set empty, which requires *every*
# tool. A record this cannot find has to make the check stricter, never more
# forgiving — the opposite would turn a broken CLI into a green verification.
declare -A REFUSED_REASON=()
REFUSAL_SOURCE=""

load_refusals() {
  local listing identifier record
  if ! command -v jq >/dev/null 2>&1; then
    REFUSAL_SOURCE="jq is not installed, so every declared tool is required"
    return 0
  fi
  if [[ -z "${MACHINE:-}" ]]; then
    REFUSAL_SOURCE="MACHINE is unset, so every declared tool is required"
    return 0
  fi

  # This machine's newest *apply*. A plan or check record carries no refusals —
  # nothing was attempted — so taking the newest run of any verb would silently
  # answer "nothing was refused" whenever the last thing anyone ran was a check.
  listing=$(dotfiles report list --json 2>/dev/null) || listing=''
  identifier=$(jq -r --arg suffix "-${MACHINE}-apply" 'map(select(endswith($suffix))) | first // empty' <<<"${listing:-[]}" 2>/dev/null || echo '')
  if [[ -z "$identifier" ]]; then
    REFUSAL_SOURCE="no apply recorded for $MACHINE, so every declared tool is required"
    return 0
  fi

  record=$(dotfiles report path "$identifier" 2>/dev/null) || record=''
  if [[ ! -f "$record" ]]; then
    REFUSAL_SOURCE="run record $identifier is unreadable, so every declared tool is required"
    return 0
  fi

  # Keyed on the address's last segment, which is the name a declaration uses:
  # `toolchains/go` is answered by `go`, `packages/custom/awscli` by `awscli`.
  # Two resources can share that segment — awscli is a brew package as well as a
  # custom installer — and it is still the right key, because this is consulted
  # only for a tool that is *absent*. Something named awscli having refused to
  # install is the explanation for no `aws` on the machine, whichever one it was.
  while IFS=$'\t' read -r name reason; do
    [[ -n "$name" ]] && REFUSED_REASON["$name"]="$reason"
  done < <(jq -r '.outcomes[] | select(.action == "refused") | "\(.address | split("/") | last)\t\(.message // "")"' "$record" 2>/dev/null)
  REFUSAL_SOURCE="$identifier"
}

# Whether an absent tool was refused by that run, under the name its declaration
# uses — which is not always the name of the binary (`awscli` installs `aws`).
was_refused() {
  local declared=${1:-}
  [[ -n "$declared" && -n "${REFUSED_REASON[$declared]+set}" ]]
}

record_refusal() {
  local shown=$1 declared=$2
  log_warning "$shown: refused by $REFUSAL_SOURCE — ${REFUSED_REASON[$declared]:-no reason recorded}"
  REFUSED_CHECKS=$((REFUSED_CHECKS + 1))
  REFUSED_TOOLS+=("$shown")
}

# ================================================================
# Helper Functions
# ================================================================

check_command() {
  local name=$1
  local version_cmd=${2:-"--version"}
  local declared=${3:-$1}
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if command -v "$name" >/dev/null 2>&1; then
    if [ "$version_cmd" != "SKIP_VERSION" ]; then
      local version
      # Add timeout to prevent hanging on commands like yazi --version
      version=$(timeout 3 "$name" "$version_cmd" 2>&1 | head -n1 || echo "unknown")
      log_success "$name: $version"
    else
      log_success "$name: installed"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  elif was_refused "$declared"; then
    record_refusal "$name" "$declared"
  else
    log_error "$name: NOT FOUND"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

check_command_at_path() {
  local name=$1
  local expected_path=$2
  local version_cmd=${3:-"--version"}
  local declared=${4:-$1}
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  # Expand ~ to $HOME
  expected_path="${expected_path/#\~/$HOME}"

  if [ -f "$expected_path" ]; then
    if [ "$version_cmd" != "SKIP_VERSION" ]; then
      local version
      version=$(timeout 3 "$expected_path" "$version_cmd" 2>&1 | head -n1 || echo "unknown")
      log_success "$name: $version (at $expected_path)"
    else
      log_success "$name: installed at $expected_path"
    fi
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    local actual_location
    actual_location=$(command -v "$name" 2>/dev/null || echo "not found")
    if [ "$actual_location" != "not found" ]; then
      # Special case: On Arch, go is installed via pacman to /usr/bin/go (acceptable)
      if [ "$name" = "go" ] && [ -f /etc/arch-release ] && [ "$actual_location" = "/usr/bin/go" ]; then
        log_success "$name: $actual_location (Arch system package)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
      else
        # Deliberately not excused by a refusal. A binary in the wrong prefix is
        # something that *did* get installed, by something nobody declared — which
        # is the failure this check exists for, and the run refusing its own
        # install is what makes a stray copy the only one left on PATH.
        log_error "$name: WRONG LOCATION - expected $expected_path, found at $actual_location"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        FAILED_TOOLS+=("$name")
      fi
    elif was_refused "$declared"; then
      record_refusal "$name" "$declared"
    else
      log_error "$name: NOT FOUND (expected at $expected_path)"
      FAILED_CHECKS=$((FAILED_CHECKS + 1))
      FAILED_TOOLS+=("$name")
    fi
  fi
}

check_file_exists() {
  local name=$1
  local path=$2
  local declared=${3:-}
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if [ -f "$path" ] || [ -d "$path" ]; then
    log_success "$name: $path"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  elif was_refused "$declared"; then
    record_refusal "$name" "$declared"
  else
    log_error "$name: NOT FOUND at $path"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("$name")
  fi
}

# ================================================================
# Verification Checks
# ================================================================

print_header "Installation Verification" "blue"

# ================================================================
# Platform Detection
# ================================================================
DETECTED_PLATFORM="unknown"
if [ -f "$HOME/.env" ]; then
  # shellcheck disable=SC1091
  source "$HOME/.env"
  DETECTED_PLATFORM=$PLATFORM
elif [ "$(uname)" = "Darwin" ]; then
  DETECTED_PLATFORM="macos"
elif grep -q "Microsoft" /proc/version 2>/dev/null; then
  DETECTED_PLATFORM="wsl"
elif [ -f /etc/arch-release ]; then
  DETECTED_PLATFORM="archlinux"
else
  DETECTED_PLATFORM="linux"
fi

echo ""
log_info "Detected platform: $DETECTED_PLATFORM"

# After ~/.env, which is where MACHINE comes from.
load_refusals
log_info "Refusals read from: ${REFUSAL_SOURCE:-nothing}"
echo ""

# ================================================================
# Everything the manifest declares
# ================================================================
# Derived from packages.yml filtered by this machine's manifest, so the checks
# cannot drift from the install. The hand-written list they replaced went stale
# in both directions at once: it still asserted `menu` and `theme-sync` months
# after both were deleted, checked vscode-html-language-server where packages.yml
# declares vscode-json-language-server, and silently never checked taplo, sass,
# fnm, broot, tldr, pre-commit, zk or atuin at all.
#
# Presence only, no version flag. A per-tool version flag is another list to keep
# right, and getting it wrong is not a finding about the machine — `cargo-binstall
# --version` reported a bogus version for exactly that reason.
verify_declared_packages() {
  # A failure, not a skip. Without MACHINE this silently checked 45 things instead
  # of 138 and still printed "All verified successfully" — a pass that means less
  # than it says is worse than no check at all.
  local manifest_name="${MACHINE:-}"
  if [[ -z "$manifest_name" ]]; then
    log_error "MACHINE is not set — cannot verify what this machine declares"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("MACHINE unset in ~/.env")
    return 1
  fi

  local rows section kind value name last_section=""
  if ! rows=$(dotfiles_python -m dotfiles.parse_packages --manifest="$manifest_name" --verify-commands 2>&1); then
    log_error "Could not read the manifest's declared commands: $rows"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    return 1
  fi

  while IFS='|' read -r section kind value name; do
    [[ -z "$value" ]] && continue
    if [[ "$section" != "$last_section" ]]; then
      print_section "${section//_/ } (declared by $manifest_name)"
      last_section="$section"
    fi
    case "$kind" in
      # `$name` is the declaration's name and `$value` the binary, which differ
      # often enough to matter — awscli installs `aws` — and the refusal the run
      # recorded is addressed by the former.
      command) check_command "$value" "SKIP_VERSION" "$name" ;;
      # Refusal-aware for the same reason as a command row, and passed through even
      # though the one path row today is `bashselfupdate`, whose script *is* staged
      # into the bundle so it cannot be refused offline. The false red would arrive
      # the day a path-evidenced installer stops being bundled, and finding it then
      # means diagnosing it from a machine rather than from this line.
      path) check_file_exists "$(basename "$value")" "${value/#\~/$HOME}" "$name" ;;
      # The same test the installer makes, so a container — which is not a real
      # WSL host and never gets the Windows clipboard bridge — is not reported as
      # a broken machine.
      command_wsl_host)
        if grep -qE "Microsoft|WSL" /proc/version 2>/dev/null; then
          check_command "$value" "SKIP_VERSION" "$name"
        else
          log_info "$value: skipped, needs a Windows host"
        fi
        ;;
      # A private repo's tool cannot install without credentials, so a machine
      # that has none is accurately described as lacking it rather than broken.
      # Reported rather than silently skipped, unlike the WSL case: credentials
      # are a state a machine can lose, and a lost `gh` login going unmentioned
      # is how these three would quietly stop being updated.
      command_github_auth)
        if [[ -n "$(github_token)" ]]; then
          check_command "$value" "SKIP_VERSION" "$name"
        else
          log_warning "$value: skipped, its repo is private and this machine has no GitHub credentials"
        fi
        ;;
    esac
  done <<<"$rows"
}

verify_declared_packages

# ================================================================
# Core Build Tools (Universal)
# ================================================================
# System packages and bootstrap runtimes: not in any manifest tool section, so
# these stay written out.
print_section "Core Build Tools (Universal)"
check_command "git"
check_command "curl"
check_command "wget"
check_command "unzip"
check_command "make"

# ================================================================
# Shell and Terminal Tools (Universal)
# ================================================================
print_section "Shell and Terminal Tools (Universal)"
check_command "zsh"
check_command "tmux"

# ================================================================
# System Utilities (Universal)
# ================================================================
print_section "System Utilities (Universal)"
check_command "tree"
check_command "htop" "--version"
check_command "jq"
check_command "glow" # Markdown renderer
check_command "duf"  # Better df

# ================================================================
# macOS-Specific Tools
# ================================================================
if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
  print_section "macOS-Specific Tools"
  check_command "duti" "SKIP_VERSION" # File association manager
fi

# ================================================================
# File Processing Tools
# ================================================================
print_section "File Processing Tools (Universal)"
check_command "ffmpeg" "-version"

# 7-Zip: Arch provides 7z, others provide 7zz
if [[ "$DETECTED_PLATFORM" == "archlinux" ]]; then
  check_command "7z" "SKIP_VERSION"
else
  check_command "7zz" "SKIP_VERSION"
fi

check_command "pdftoppm" "-v"
check_command "convert" "-version" # imagemagick
check_command "chafa"

# ================================================================
# Language Runtimes and Managers
# ================================================================
print_section "Language Runtimes (Universal)"

# Written out rather than derived, because a runtime is in no manifest tool
# section — `registry.ToolchainProvider` derives which ones a machine needs from
# the tool sections that need one. The fourth argument is that runtime's name in
# the plan, so a refused toolchain explains every binary it would have placed:
# `toolchains/rust` is one refusal answering for rustup, cargo and rustc.
check_command_at_path "go" "/usr/local/go/bin/go" "version" "go"

# Node.js (system package via brew/pacman)
check_command "node"
check_command "npm"

# Python (via uv)
check_command "uv" "--version" "uv"

# Rust
check_command "rustup" "--version" "rust"
check_command "cargo" "--version" "rust"
check_command "rustc" "--version" "rust"

# cargo-binstall is a precondition of the cargo provider rather than anything a
# manifest declares, so it is expected exactly where that provider went to
# crates.io for a package — which is where `cargo` itself came from. An offline
# machine takes every Rust CLI from its bundle and needs no binstall to do it, so
# asserting one unconditionally described a machine nobody was trying to build.
if command -v cargo >/dev/null 2>&1; then
  check_command "cargo-binstall" "-V"
else
  log_info "cargo-binstall: skipped, there is no cargo on this machine to bootstrap it for"
fi

# Note: Lua/LuaJIT not checked - Neovim uses hererocks via lazy.nvim for Lua 5.1

# ================================================================
# Docker (Platform-Specific)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Docker (Skip on WSL - uses Windows Docker Desktop)"

  # OrbStack (macOS only)
  if [[ "$DETECTED_PLATFORM" == "macos" ]]; then
    check_command "orbctl"
  fi

  # Docker CLI and compose (all non-WSL platforms)
  check_command "docker"

  # Check docker compose V2
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version 2>&1 | head -n1)
    log_success "docker compose: $COMPOSE_VERSION"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
  else
    log_error "docker compose: NOT WORKING"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("docker-compose")
  fi
else
  print_section "Docker (Skipped on WSL)"
  log_info "WSL uses Windows Docker Desktop (not checked)"
fi

# ================================================================
# Git Tools
# ================================================================
print_section "Git Tools (Universal)"
check_command "gh"

# ================================================================
# Second binaries and symlinked apps
# ================================================================
# Not manifest entries: `ya` is yazi's companion binary shipped by the same
# release, and apps/ scripts are symlinked by the symlink manager rather than
# installed by any packages.yml section.
print_section "Companion Binaries and Symlinked Apps (Universal)"
check_command_at_path "ya" "$HOME/.local/bin/ya"
check_command "notes" "SKIP_VERSION"

# ================================================================
# Claude Code (Universal - except WSL)
# ================================================================
if [[ "$DETECTED_PLATFORM" != "wsl" ]]; then
  print_section "Claude Code (Universal - except WSL)"
  check_command "claude"
fi

# ================================================================
# System Package Linters
# ================================================================
print_section "Shell Script Tools (Universal)"
check_command "shfmt"

# ================================================================
# Shell Configuration
# ================================================================
print_section "Shell Configuration (Universal)"
check_file_exists "zshrc" "$HOME/.config/zsh/.zshrc"
check_file_exists "zsh plugins dir" "$HOME/.config/zsh/plugins"

# Check for shell plugins (git-open, zsh-vi-mode, forgit, zsh-syntax-highlighting)
check_file_exists "git-open plugin" "$HOME/.config/zsh/plugins/git-open"
check_file_exists "zsh-vi-mode plugin" "$HOME/.config/zsh/plugins/zsh-vi-mode"
check_file_exists "forgit plugin" "$HOME/.config/zsh/plugins/forgit"
check_file_exists "zsh-syntax-highlighting plugin" "$HOME/.config/zsh/plugins/zsh-syntax-highlighting"

# ================================================================
# Tmux Configuration
# ================================================================
print_section "Tmux Configuration (Universal)"
check_file_exists "tmux.conf" "$HOME/.config/tmux/tmux.conf"

# ================================================================
# Git Configuration
# ================================================================
print_section "Git Configuration (Universal)"
check_file_exists "gitconfig" "$HOME/.gitconfig"

# ================================================================
# Neovim Configuration
# ================================================================
print_section "Neovim Configuration (Universal)"
check_file_exists "init.lua" "$HOME/.config/nvim/init.lua"

# ================================================================
# Tmux Plugins (TPM)
# ================================================================
print_section "Tmux Plugins - TPM (Universal)"
check_file_exists "TPM" "$HOME/.config/tmux/plugins/tpm"
# Check if at least one configured plugin is installed
check_file_exists "tmux-fzf plugin" "$HOME/.config/tmux/plugins/tmux-fzf"

# ================================================================
# Neovim Plugins (Lazy.nvim)
# ================================================================
print_section "Neovim Plugins - Lazy.nvim (Universal)"
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
# Check if lazy.nvim is installed
if [ -d "$HOME/.local/share/nvim/lazy/lazy.nvim" ]; then
  echo -e "  ${GREEN}✓${NC} Lazy.nvim: installed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  echo -e "  ${RED}✗${NC} Lazy.nvim: NOT FOUND"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("lazy.nvim")
fi

# Check if treesitter is installed (common plugin)
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if [ -d "$HOME/.local/share/nvim/lazy/nvim-treesitter" ]; then
  echo -e "  ${GREEN}✓${NC} nvim-treesitter: installed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  echo -e "  ${RED}✗${NC} nvim-treesitter: NOT FOUND"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("nvim-treesitter")
fi

# Test that neovim can start headless without errors
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if timeout 5 nvim --headless +qa 2>&1 | grep -q "error"; then
  echo -e "  ${RED}✗${NC} Neovim headless test: ERRORS DETECTED"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("neovim-headless")
else
  echo -e "  ${GREEN}✓${NC} Neovim headless test: passed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# ================================================================
# Yazi File Manager
# ================================================================
print_section "Yazi Functionality (Universal)"
# Test that yazi can start and exit without errors
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if timeout 2 yazi --clear-cache 2>&1 | grep -qi "error"; then
  echo -e "  ${RED}✗${NC} Yazi startup test: ERRORS DETECTED"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("yazi-startup")
else
  echo -e "  ${GREEN}✓${NC} Yazi startup test: passed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# ================================================================
# Package Management Scripts
# ================================================================
print_section "Package Management Scripts (Universal)"

# The catalog reader has to be reachable, or every declared-package check above
# is silently vacuous rather than failing.
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if dotfiles_python -m dotfiles.parse_packages --type=system --manager=apt >/dev/null 2>&1; then
  log_success "parse_packages.py: working (yaml module available)"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
  log_error "parse_packages.py: FAILED (yaml module missing or script error)"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
  FAILED_TOOLS+=("parse_packages.py")
fi

# ================================================================
# Flatpak Apps (Arch only, skip in Docker)
# ================================================================
verify_declared_flatpaks() {
  local declared installed app

  # Every id the manifest asks for, checked individually. This grepped
  # `flatpak list` for "zen" as a "sample app" — and zen-browser is an AUR
  # package, never a flatpak, so the one hand-written name here was wrong about
  # what it was naming and reported a false failure on a converged machine for as
  # long as it existed. The declared apps are DBeaver and Discord, and a sample of
  # one could not have told you which of the two was missing anyway.
  if ! declared=$(dotfiles_python -m dotfiles.parse_packages --type=flatpak --manifest="${MACHINE:-}" --format=names 2>/dev/null); then
    log_error "Could not read the manifest's declared flatpak apps"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("flatpak declaration")
    return 1
  fi
  [[ -z "${declared//[[:space:]]/}" ]] && return 0

  print_section "Flatpak Apps (declared by ${MACHINE:-this machine})"
  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
  if ! command -v flatpak >/dev/null 2>&1; then
    log_error "flatpak: NOT FOUND, and this machine declares flatpak apps"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    FAILED_TOOLS+=("flatpak")
    return 1
  fi
  log_success "flatpak: installed"
  PASSED_CHECKS=$((PASSED_CHECKS + 1))

  installed=$(flatpak list --app --columns=application 2>/dev/null || echo '')
  while read -r app; do
    [[ -z "$app" ]] && continue
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if grep -qxF "$app" <<<"$installed"; then
      log_success "flatpak app: $app"
      PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
      log_error "flatpak app: $app NOT FOUND"
      FAILED_CHECKS=$((FAILED_CHECKS + 1))
      FAILED_TOOLS+=("flatpak:$app")
    fi
  done <<<"$declared"
}

# Not gated on a platform: `flatpak_apps` is opt-in per machine rather than
# something a package manager carries, so a manifest declaring none is checked for
# none wherever it runs. Still skipped in a container, where no session bus means
# no flatpak can be installed in the first place.
if [[ "${DOTFILES_DOCKER_TEST:-}" != "true" ]]; then
  verify_declared_flatpaks
fi

# ================================================================
# Summary
# ================================================================

print_header "Summary" "blue"

echo "Total: ${TOTAL_CHECKS} checks"
print_green "Passed: ${PASSED_CHECKS}"

# Named even when the run is green, because a refusal is a real absence and a
# tally that hid it would report a machine as fully verified while it is missing
# four tools for a reason someone may want to revisit.
if [ $REFUSED_CHECKS -gt 0 ]; then
  print_yellow "Refused: ${REFUSED_CHECKS} (the install reached these and wrote nothing, on purpose)"
  for tool in "${REFUSED_TOOLS[@]}"; do
    echo "  - $tool"
  done
fi

if [ $FAILED_CHECKS -gt 0 ]; then
  print_red "Failed: ${FAILED_CHECKS}"
  echo ""
  print_red "Failed tools:"
  for tool in "${FAILED_TOOLS[@]}"; do
    echo "  • $tool"
  done
  echo ""
  log_info "What each install decided, with its reason: dotfiles report latest"
  echo ""
  print_header_error "Verification FAILED"
  exit 1
fi

echo ""
if [ $REFUSED_CHECKS -gt 0 ]; then
  print_header_success "Verified — everything this machine's install could deliver"
else
  print_header_success "All verified successfully"
fi
exit 0
