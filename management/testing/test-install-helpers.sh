#!/usr/bin/env bash
# ================================================================
# Shared Testing Helper Functions
# ================================================================
# Common functions used across all platform testing scripts
# Source this file at the beginning of platform-specific scripts
# ================================================================

# Ensure this file is sourced, not executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Error: This file should be sourced, not executed directly"
  echo "Usage: source test-install-helpers.sh"
  exit 1
fi

# ================================================================
# FORMATTING (if not already sourced)
# ================================================================

if ! command -v print_header &>/dev/null; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
  source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"
fi

# ================================================================
# TIMING FUNCTIONS
# ================================================================

# Timing arrays (must be declared in calling script)
# declare -a STEP_NAMES
# declare -a STEP_TIMES

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

# Function to log section headers with timestamp
log_section() {
  echo ""
  print_header "[$(date '+%Y-%m-%d %H:%M:%S')] $*" "blue"
}

# Function to log timing after each step
log_timing() {
  local step_name=$1
  local elapsed=$2
  local formatted_time
  formatted_time=$(format_time "$elapsed")
  echo ""
  print_info "⏱  $step_name completed in $formatted_time"
  echo ""
}

# Function to print timing summary
print_timing_summary() {
  local overall_elapsed=$1

  echo ""
  print_section "Timing Summary" "cyan"
  echo ""
  for i in "${!STEP_NAMES[@]}"; do
    formatted_time=$(format_time "${STEP_TIMES[$i]}")
    printf "  %s Step %d: %-20s %s\n" "$(print_green "✓")" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
  done
  echo "  ─────────────────────────────────────────────"
  formatted_total=$(format_time "$overall_elapsed")
  printf "  %-27s %s\n" "Total time:" "$(print_cyan "$formatted_total")"
  echo ""
}

# ================================================================
# DOCKER HELPERS
# ================================================================

# Check if Docker is running
check_docker() {
  if ! docker info >/dev/null 2>&1; then
    die "Docker is not running. Please start Docker Desktop and try again."
  fi
}

# Check if Docker image exists
docker_image_exists() {
  local image=$1
  docker image inspect "$image" >/dev/null 2>&1
}

# Check if container exists
docker_container_exists() {
  local container=$1
  docker ps -a --format '{{.Names}}' | grep -q "^${container}$"
}

# Check if container is running
docker_container_running() {
  local container=$1
  docker ps --format '{{.Names}}' | grep -q "^${container}$"
}

# Start stopped container
docker_start_container() {
  local container=$1
  if docker_container_exists "$container" && ! docker_container_running "$container"; then
    echo "Container is stopped, starting..."
    docker start "$container"
  fi
}

# ================================================================
# VERIFICATION HELPERS
# ================================================================

# Run verification script in container
run_verification() {
  local container=$1
  local home_dir=$2
  local dotfiles_path=$3

  log_section "Verifying Installation"
  echo "Running comprehensive verification in fresh shell..."
  echo "(This tests that all tools are properly configured and in PATH)"
  echo ""

  docker exec "$container" bash -c "
    ZSHDOTDIR=${home_dir}/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; bash --norc ${dotfiles_path}/management/verify-installation.sh\"
  "
}

# Run update-all task in container
run_update_test() {
  local container=$1
  local home_dir=$2
  local dotfiles_path=$3
  local update_task=$4

  log_section "Testing update-all Task"
  echo "Running task ${update_task} to verify update functionality..."
  echo ""

  docker exec "$container" bash -c "
    cd ${dotfiles_path}
    ZSHDOTDIR=${home_dir}/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; task ${update_task}\"
  "
}

# ================================================================
# CLEANUP HELPERS
# ================================================================

# Cleanup Docker container
cleanup_container() {
  local container=$1
  local keep_flag=${2:-false}

  if [[ "$keep_flag" == false ]]; then
    if docker_container_exists "$container"; then
      echo ""
      print_info "Cleaning up container: $container"
      docker rm -f "$container" >/dev/null 2>&1 || true
    fi
  else
    echo ""
    print_info "Container kept for debugging: $container"
    echo "  • Shell into container: docker exec -it $container bash"
    echo "  • View logs: docker logs $container"
    echo "  • Remove container: docker rm -f $container"
  fi
}

# ================================================================
# ENVIRONMENT SETUP HELPERS
# ================================================================

# Create .env file in container
create_container_env() {
  local container=$1
  local platform=$2
  local home_dir=$3

  docker exec "$container" bash -c "cat > ${home_dir}/.env <<EOF
PLATFORM=${platform}
NVIM_AI_ENABLED=false
DOTFILES_DOCKER_TEST=true
EOF"
}

# Copy dotfiles to writable location in container
copy_dotfiles_writable() {
  local container=$1
  local source_path=$2
  local target_path=$3

  echo "Copying dotfiles to writable location..."
  docker exec "$container" bash -c "cp -r ${source_path} ${target_path}"
}
