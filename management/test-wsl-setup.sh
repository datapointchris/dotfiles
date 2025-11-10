#!/usr/bin/env bash

set -e  # Exit on error

VM_NAME="dotfiles-wsl-test"
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${DOTFILES_DIR}/test-wsl-setup.log"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log with timestamps
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function to log section headers
log_section() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
}

# Clear previous log and start fresh
true > "$LOG_FILE"

echo -e "${BLUE}Log file: ${LOG_FILE}${NC}"
echo ""

# Launch VM
{
  log_section "STEP 1/4: Launching Multipass VM"
  multipass launch --name "$VM_NAME" --cpus 10 --mem 32G
} 2>&1 | tee -a "$LOG_FILE"

# Clone dotfiles
{
  log_section "STEP 2/4: Cloning dotfiles repository"
  multipass exec "$VM_NAME" -- git clone https://github.com/user/dotfiles.git
} 2>&1 | tee -a "$LOG_FILE"

# Run WSL setup
{
  log_section "STEP 3/4: Running WSL setup script"
  multipass exec "$VM_NAME" -- bash dotfiles/management/wsl-setup.sh
} 2>&1 | tee -a "$LOG_FILE"

# Verify installation
{
  log_section "STEP 4/4: Verifying installation"
  multipass exec "$VM_NAME" -- bash -c "cd dotfiles && task verify"
} 2>&1 | tee -a "$LOG_FILE"

# Summary
{
  log_section "SETUP COMPLETE"
  echo -e "${GREEN}✓ WSL setup test completed successfully${NC}"
  echo ""
  echo "VM name: $VM_NAME"
  echo "Log file: $LOG_FILE"
  echo ""
  echo "Next steps:"
  echo "  - Review log: less $LOG_FILE"
  echo "  - Shell into VM: multipass shell $VM_NAME"
  echo "  - Stop VM: multipass stop $VM_NAME"
  echo "  - Delete VM: multipass delete $VM_NAME --purge"
} 2>&1 | tee -a "$LOG_FILE"
