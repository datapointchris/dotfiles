#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
source "$DOTFILES_DIR/install/common/lib/python.sh"

OS=$(detect_os)
ARCH=$(detect_arch)

awscli_zip_url() {
  local url_base
  url_base=$(dotfiles_python -m dotfiles.parse_packages \
    --custom-installer awscli --field url) || return 1
  case $ARCH in
    amd64) echo "${url_base}/awscli-exe-linux-x86_64.zip" ;;
    arm64) echo "${url_base}/awscli-exe-linux-aarch64.zip" ;;
    *) return 1 ;;
  esac
}

# Ahead of the platform branches so nothing has logged to stdout yet: the caller
# parses this line. Exits 1 on macOS, where awscli comes from Homebrew and there
# is no download URL to report.
if [[ "${1:-}" == "--print-url" ]]; then
  [[ "$OS" == "darwin" ]] && exit 1
  url=$(awscli_zip_url) || exit 1
  echo "awscli|latest|$url"
  exit 0
fi

if [[ "$OS" == "darwin" ]]; then
  if command -v aws >/dev/null 2>&1; then
    CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    if [[ "$UPDATE_MODE" == "true" ]]; then
      log_success "awscli at version $CURRENT_VERSION (managed by Homebrew)"
    else
      log_success "awscli already installed: $CURRENT_VERSION (managed by Homebrew)"
    fi
  else
    if [[ "$UPDATE_MODE" == "true" ]]; then
      log_info "AWS CLI not installed"
      log_info "macOS: Install via Homebrew: brew install awscli"
    else
      log_info "macOS: AWS CLI will be installed via Homebrew"
      log_info "Add 'awscli' to packages.yml and run: task macos:install-packages"
    fi
  fi
  exit 0
fi

# Linux: Version checking
if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    skip_update_for_absent_tool "awscli"
  else
    CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    log_info "Current version: $CURRENT_VERSION"
    log_info "AWS installer will check for updates..."
  fi
else
  if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [ -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
    CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    log_success "Current version: $CURRENT_VERSION, skipping"
    exit 0
  fi

  if [ ! -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
    ALTERNATE_LOCATION=$(command -v aws)
    log_warning "aws found at $ALTERNATE_LOCATION"
    log_info "AWS CLI official installer will be used"
  fi
fi

case $OS in
  linux)
    log_info "Platform: Linux ($ARCH)"

    ZIP_URL=$(awscli_zip_url) \
      || {
        log_error "Could not build the awscli download URL for $ARCH"
        exit 1
      }

    ZIP_FILE="/tmp/awscliv2.zip"
    EXTRACT_DIR="/tmp/aws-cli-install"

    log_info "Downloading AWS CLI..."
    if ! curl -fsSL "$ZIP_URL" -o "$ZIP_FILE"; then
      output_failure_data "aws" "$ZIP_URL" "latest" "Download failed"
      log_warning "AWS CLI installation failed (see summary)"
      exit 1
    fi

    log_info "Extracting installer..."
    rm -rf "$EXTRACT_DIR"
    mkdir -p "$EXTRACT_DIR"
    unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR"

    # Install to user directory (no sudo needed)
    log_info "Installing AWS CLI v2 to ~/.local/..."
    if ! "$EXTRACT_DIR/aws/install" --install-dir "$HOME/.local/aws-cli" --bin-dir "$HOME/.local/bin" --update; then
      output_failure_data "aws" "$ZIP_URL" "latest" "AWS installer failed"
      rm -rf "$ZIP_FILE" "$EXTRACT_DIR"
      log_warning "AWS CLI installation failed (see summary)"
      exit 1
    fi

    rm -rf "$ZIP_FILE" "$EXTRACT_DIR"
    ;;

  *)
    log_error "Unsupported OS: $OS"
    exit 1
    ;;
esac

if command -v aws >/dev/null 2>&1; then
  INSTALLED_VERSION=$(aws --version 2>&1)
  log_success "$INSTALLED_VERSION"
else
  output_failure_data "aws" "unknown" "latest" "Installation verification failed"
  log_warning "AWS CLI installation verification failed (see summary)"
  exit 1
fi
