#!/usr/bin/env bash

set -eou pipefail  # Exit on error

# Show usage
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test WSL setup script in a Multipass VM"
  echo ""
  echo "Options:"
  echo "  -d, --dev      Development mode: Transfer local dotfiles (test uncommitted changes)"
  echo "  -r, --reuse    Reuse last VM (faster iteration, tests idempotency)"
  echo "  -h, --help     Show this help message"
  echo ""
  echo "Default (no flags): Production mode - clone from GitHub (mirrors real installation)"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")           # Fresh VM, clone from GitHub"
  echo "  $(basename "$0") -d        # Fresh VM, transfer local changes"
  echo "  $(basename "$0") -r        # Reuse last VM, pull from GitHub"
  echo "  $(basename "$0") -d -r     # Reuse last VM, transfer local changes"
  exit 0
fi

# Parse arguments
DEV_MODE=false
REUSE_VM=false
for arg in "$@"; do
  case $arg in
    -d|--dev)
      DEV_MODE=true
      shift
      ;;
    -r|--reuse)
      REUSE_VM=true
      shift
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAST_VM_FILE="${DOTFILES_DIR}/.last-test-vm"
VM_CPUS=10
VM_MEMORY="16G"
VM_DISK="50G"

# Determine VM name
VM_FOUND=false
if [[ "$REUSE_VM" == true ]]; then
  if [[ -f "$LAST_VM_FILE" ]]; then
    VM_NAME=$(cat "$LAST_VM_FILE")
    # Verify VM exists
    if multipass list | grep -q "^${VM_NAME}"; then
      VM_FOUND=true
      echo "Found previous VM: $VM_NAME"
    else
      echo "Last VM '$VM_NAME' not found, creating new VM..."
    fi
  else
    echo "No previous VM found, creating new VM..."
  fi
fi

# Create new VM if not found or not reusing
if [[ "$VM_FOUND" == false ]]; then
  VM_NAME="dotfiles-wsl-test-$(date '+%Y-%m-%d-%H%M%S')"
  # Save VM name for potential reuse
  echo "$VM_NAME" > "$LAST_VM_FILE"
  REUSE_VM=false  # Force fresh VM creation
fi

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
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $*${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

# Overwrite log file (not append)
: > "$LOG_FILE"

# Display mode
MODE_DESC="PRODUCTION mode (GitHub)"
if [[ "$DEV_MODE" == true ]]; then
  MODE_DESC="DEVELOPMENT mode (local files)"
fi
if [[ "$REUSE_VM" == true ]]; then
  MODE_DESC="$MODE_DESC + REUSING VM"
fi

echo -e "${BLUE}Running in ${MODE_DESC}${NC}"
echo -e "${BLUE}VM: ${VM_NAME}${NC}"
echo -e "${BLUE}Log file: ${LOG_FILE}${NC}"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# STEP 1: Launch VM (skip if reusing)
if [[ "$REUSE_VM" == false ]]; then
  STEP_START=$(date +%s)
  {
    log_section "STEP 1/4: Launching Multipass VM"
    multipass launch --name "$VM_NAME" --cpus ${VM_CPUS} --memory ${VM_MEMORY} --disk ${VM_DISK}
  } 2>&1 | tee -a "$LOG_FILE"
  STEP_END=$(date +%s)
  STEP_ELAPSED=$((STEP_END - STEP_START))
  STEP_NAMES+=("Launch VM")
  STEP_TIMES+=("$STEP_ELAPSED")
  {
    log_timing "Step 1: Launch VM" "$STEP_ELAPSED"
  } 2>&1 | tee -a "$LOG_FILE"
else
  {
    log_section "STEP 1/4: Reusing existing VM"
    echo "Using VM: $VM_NAME"
    echo ""
    multipass list | grep "$VM_NAME"
  } 2>&1 | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
fi

# STEP 2: Get dotfiles (clone/pull/transfer based on mode)
# shellcheck disable=SC2030,SC2031  # STEP_NAME set in subshell but works correctly
STEP_START=$(date +%s)
if [[ "$DEV_MODE" == true ]]; then
  {
    log_section "STEP 2/4: Transferring local dotfiles to VM"
    # Remove old dotfiles if reusing to ensure clean transfer
    if [[ "$REUSE_VM" == true ]]; then
      echo "Removing old dotfiles directory..."
      multipass exec "$VM_NAME" -- rm -rf dotfiles
    fi
    # Exclude build artifacts and virtual environments
    echo "Transferring dotfiles (excluding .venv, node_modules, etc.)..."
    rsync -a --exclude='.venv' --exclude='node_modules' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' "$DOTFILES_DIR/" "$DOTFILES_DIR/.tmp-transfer/"
    multipass transfer -r "$DOTFILES_DIR/.tmp-transfer" "$VM_NAME":dotfiles
    rm -rf "$DOTFILES_DIR/.tmp-transfer"
  } 2>&1 | tee -a "$LOG_FILE"
  STEP_NAME="Transfer dotfiles"
else
  {
    if [[ "$REUSE_VM" == true ]]; then
      log_section "STEP 2/4: Updating dotfiles from GitHub"
      # Check if dotfiles exists
      if multipass exec "$VM_NAME" -- test -d dotfiles; then
        echo "Dotfiles directory exists, pulling latest changes..."
        multipass exec "$VM_NAME" -- bash -c "cd dotfiles && git pull"
        # shellcheck disable=SC2030
        STEP_NAME="Pull dotfiles"
      else
        echo "Dotfiles directory not found, cloning..."
        multipass exec "$VM_NAME" -- git clone https://github.com/datapointchris/dotfiles.git
        STEP_NAME="Clone dotfiles"
      fi
    else
      log_section "STEP 2/4: Cloning dotfiles from GitHub"
      multipass exec "$VM_NAME" -- git clone https://github.com/datapointchris/dotfiles.git
      STEP_NAME="Clone dotfiles"
    fi
  } 2>&1 | tee -a "$LOG_FILE"
fi
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
# shellcheck disable=SC2031  # STEP_NAME set in subshell above but works correctly
STEP_NAMES+=("$STEP_NAME")
STEP_TIMES+=("$STEP_ELAPSED")
{
  # shellcheck disable=SC2031
  log_timing "Step 2: $STEP_NAME" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# STEP 3: Run WSL setup
STEP_START=$(date +%s)
{
  log_section "STEP 3/4: Running WSL setup script"
  echo "Creating ~/.env for testing..."
  multipass exec "$VM_NAME" -- bash -c 'cat > ~/.env <<EOF
PLATFORM=wsl
NVIM_AI_ENABLED=false
EOF'
  echo ""
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
  echo "Running comprehensive verification in fresh shell..."
  echo "(This tests that all tools are properly configured and in PATH)"
  echo ""

  # Run verification script in a fresh zsh shell
  # Explicitly source .zshrc to load PATH (zsh -c doesn't auto-source .zshrc)
  # Use bash --norc to inherit PATH from zsh without sourcing .bashrc
  # This ensures the environment is loaded naturally without hardcoded PATH
  # shellcheck disable=SC2016  # $HOME and \$ZSHDOTDIR need to expand on remote VM
  multipass exec "$VM_NAME" -- bash -c 'ZSHDOTDIR=$HOME/.config/zsh zsh -c "source \$ZSHDOTDIR/.zshrc 2>/dev/null; bash --norc dotfiles/management/verify-installation.sh"'
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
  echo ""
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN} ✅ Setup Complete${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "${CYAN}Timing Summary${NC}"
  echo ""
  for i in "${!STEP_NAMES[@]}"; do
    formatted_time=$(format_time "${STEP_TIMES[$i]}")
    printf "  ${GREEN}✓${NC} Step %d: %-20s %s\n" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
  done
  echo "  ─────────────────────────────────────────────"
  formatted_total=$(format_time "$OVERALL_ELAPSED")
  printf "  %-27s ${CYAN}%s${NC}\n" "Total time:" "$formatted_total"
  echo ""
  echo -e "${CYAN}VM Information${NC}"
  echo ""
  echo "  VM name: $VM_NAME"
  echo "  Log file: $LOG_FILE"
  echo ""
  echo -e "${CYAN}Next steps:${NC}"
  echo "  • Review log: less $LOG_FILE"
  echo "  • Shell into VM: multipass shell $VM_NAME"
  echo "  • Stop VM: multipass stop $VM_NAME"
  echo "  • Delete VM: multipass delete $VM_NAME --purge"
  echo ""
} 2>&1 | tee -a "$LOG_FILE"
