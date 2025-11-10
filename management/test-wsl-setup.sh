#!/usr/bin/env bash

set -e  # Exit on error

VM_NAME="dotfiles-wsl-test"
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${DOTFILES_DIR}/test-wsl-setup.log"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES

# Function to format seconds as MM:SS
format_time() {
  local total_seconds=$1
  local minutes=$((total_seconds / 60))
  local seconds=$((total_seconds % 60))
  printf "%02d:%02d" $minutes $seconds
}

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

# Function to log timing after each step
log_timing() {
  local step_name=$1
  local elapsed=$2
  local formatted_time
  formatted_time=$(format_time "$elapsed")
  echo ""
  echo -e "${CYAN}⏱  $step_name completed in $formatted_time${NC}"
  echo ""
}

# Clear previous log and start fresh
true > "$LOG_FILE"

echo -e "${BLUE}Log file: ${LOG_FILE}${NC}"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# STEP 1: Launch VM
STEP_START=$(date +%s)
{
  log_section "STEP 1/4: Launching Multipass VM"
  multipass launch --name "$VM_NAME" --cpus 10 --mem 32G
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Launch VM")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 1: Launch VM" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# STEP 2: Clone dotfiles
STEP_START=$(date +%s)
{
  log_section "STEP 2/4: Cloning dotfiles repository"
  multipass exec "$VM_NAME" -- git clone https://github.com/datapointchris/dotfiles.git
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Clone dotfiles")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 2: Clone dotfiles" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# STEP 3: Run WSL setup
STEP_START=$(date +%s)
{
  log_section "STEP 3/4: Running WSL setup script"
  multipass exec "$VM_NAME" -- bash dotfiles/management/wsl-setup.sh
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("WSL setup")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 3: WSL setup" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# STEP 4: Verify installation
STEP_START=$(date +%s)
{
  log_section "STEP 4/4: Verifying installation"
  multipass exec "$VM_NAME" -- bash -c "cd dotfiles && task verify"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Verification")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 4: Verification" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# Calculate overall time
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

# Summary
{
  log_section "SETUP COMPLETE"
  echo -e "${GREEN}✓ WSL setup test completed successfully${NC}"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "TIMING SUMMARY"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  for i in "${!STEP_NAMES[@]}"; do
    formatted_time=$(format_time "${STEP_TIMES[$i]}")
    printf "  Step %d: %-20s %s\n" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
  done
  echo "  ─────────────────────────────────────────────"
  formatted_total=$(format_time "$OVERALL_ELAPSED")
  printf "  %-27s %s\n" "Total time:" "$formatted_total"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "VM INFORMATION"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "  VM name: $VM_NAME"
  echo "  Log file: $LOG_FILE"
  echo ""
  echo "Next steps:"
  echo "  - Review log: less $LOG_FILE"
  echo "  - Shell into VM: multipass shell $VM_NAME"
  echo "  - Stop VM: multipass stop $VM_NAME"
  echo "  - Delete VM: multipass delete $VM_NAME --purge"
} 2>&1 | tee -a "$LOG_FILE"
