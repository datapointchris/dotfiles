#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

print_header() {
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test all GitHub release installers in Docker containers"
  echo ""
  echo "Options:"
  echo "  --keep-on-failure  Keep containers that fail (for debugging)"
  echo "  -h, --help         Show this help message"
  echo ""
  echo "Tests 13 GitHub release installers:"
  echo "  duf, fzf, glow, lazygit, neovim, shellcheck, tenv,"
  echo "  terraformer, terrascan, tflint, trivy, yazi, zk"
  exit 0
fi

KEEP_ON_FAILURE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --keep-on-failure)
      KEEP_ON_FAILURE=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

# Map installer names to binary names
# Format: "installer:binary"
declare -a INSTALLERS=(
  "duf:duf"
  "fzf:fzf"
  "glow:glow"
  "lazygit:lazygit"
  "neovim:nvim"
  "shellcheck:shellcheck"
  "tenv:tenv"
  "terraformer:terraformer"
  "terrascan:terrascan"
  "tflint:tflint"
  "trivy:trivy"
  "yazi:yazi"
  "zk:zk"
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASSED=0
FAILED=0
declare -a FAILED_TESTS=()

print_header "Testing All GitHub Release Installers"

log_info "Total installers to test: ${#INSTALLERS[@]}"
log_info "Base image: dotfiles-test-base:ubuntu-24.04"

START_TIME=$(date +%s)

for entry in "${INSTALLERS[@]}"; do
  IFS=':' read -r installer binary <<< "$entry"

  echo ""
  echo "────────────────────────────────────────────────────────────────"
  log_info "Testing: $installer (binary: $binary)"
  echo "────────────────────────────────────────────────────────────────"

  INSTALLER_PATH="management/common/install/github-releases/${installer}.sh"

  if [[ "$KEEP_ON_FAILURE" == "true" ]]; then
    if "$SCRIPT_DIR/run-installer-test.sh" "$INSTALLER_PATH" --validate "$binary" --keep; then
      PASSED=$((PASSED + 1))
      log_success "✓ $installer passed"
    else
      FAILED=$((FAILED + 1))
      FAILED_TESTS+=("$installer")
      log_error "✗ $installer failed"
    fi
  else
    if "$SCRIPT_DIR/run-installer-test.sh" "$INSTALLER_PATH" --validate "$binary"; then
      PASSED=$((PASSED + 1))
      log_success "✓ $installer passed"
    else
      FAILED=$((FAILED + 1))
      FAILED_TESTS+=("$installer")
      log_error "✗ $installer failed"
    fi
  fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Final summary
echo ""
print_header "Test Summary"

log_info "Total tests: ${#INSTALLERS[@]}"
log_success "Passed: $PASSED"

if [[ $FAILED -gt 0 ]]; then
  log_error "Failed: $FAILED"
  echo ""
  log_info "Failed tests:"
  for test in "${FAILED_TESTS[@]}"; do
    echo "  - $test"
  done
else
  log_success "All tests passed!"
fi

log_info "Total duration: ${DURATION}s ($((DURATION / 60))m $((DURATION % 60))s)"

if [[ $FAILED -gt 0 ]]; then
  exit 1
else
  exit 0
fi
