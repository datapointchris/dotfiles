# shellcheck shell=bash
# Unit tests for failure registry functions in program-helpers.sh

# Get dotfiles directory - ShellSpec runs from project root
DOTFILES_DIR="${DOTFILES_DIR:-$PWD}"
if [[ ! -f "$DOTFILES_DIR/install.sh" ]]; then
  # We're probably in tests/ directory, go up one
  DOTFILES_DIR="$(cd "$DOTFILES_DIR/.." && pwd)"
fi
export DOTFILES_DIR
export TERM=${TERM:-xterm}

# Test helper functions
source_program_helpers() {
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"
}

create_mock_failure_registry() {
  export DOTFILES_FAILURE_REGISTRY="/tmp/dotfiles-test-failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"
}

cleanup_mock_failure_registry() {
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && [[ -d "$DOTFILES_FAILURE_REGISTRY" ]]; then
    rm -rf "$DOTFILES_FAILURE_REGISTRY"
  fi
  unset DOTFILES_FAILURE_REGISTRY
}

create_sample_failure() {
  local tool_name="$1"
  local url="${2:-https://github.com/example/repo/releases/download/v1.0/tool.tar.gz}"
  local version="${3:-v1.0}"
  local reason="${4:-Download failed}"

  local manual_steps="1. Download in your browser:
   $url

2. After downloading:
   tar -xzf ~/Downloads/${tool_name}.tar.gz
   mv ${tool_name} ~/.local/bin/
   chmod +x ~/.local/bin/${tool_name}

3. Verify:
   ${tool_name} --version"

  {
    echo "TOOL='$tool_name'"
    echo "URL='$url'"
    echo "VERSION='$version'"
    echo "REASON='$reason'"
    printf "MANUAL_STEPS=%s\n" "$(printf '%q' "$manual_steps")"
  } > "$DOTFILES_FAILURE_REGISTRY/$(date +%s)-${tool_name}.txt"
}

Describe 'Failure Registry Functions'
  Describe 'init_failure_registry()'
    Before source_program_helpers

    It 'creates registry directory'
      When call init_failure_registry
      The variable DOTFILES_FAILURE_REGISTRY should be defined
      The path "$DOTFILES_FAILURE_REGISTRY" should be directory
    End
  End

  Describe 'report_failure()'
    Before create_mock_failure_registry
    After cleanup_mock_failure_registry
    BeforeEach source_program_helpers

    It 'writes failure file'
      When call report_failure "test-tool" "https://example.com/test.tar.gz" "v1.0" "Manual steps" "Download failed"
      The status should be success
    End

    It 'includes required fields'
      report_failure "yazi" "https://example.com/yazi.zip" "v2.0" "Steps" "Network timeout"
      failure_file=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*-yazi.txt" -type f | head -1)
      The contents of file "$failure_file" should include "TOOL='yazi'"
      The contents of file "$failure_file" should include "URL='https://example.com/yazi.zip'"
      The contents of file "$failure_file" should include "VERSION='v2.0'"
      The contents of file "$failure_file" should include "REASON='Network timeout'"
    End

    It 'skips when registry not set'
      unset DOTFILES_FAILURE_REGISTRY
      When call report_failure "test" "url" "v1" "steps" "error"
      The status should be success
    End
  End

  Describe 'display_failure_summary()'
    Before create_mock_failure_registry
    After cleanup_mock_failure_registry
    BeforeEach source_program_helpers

    It 'returns success when no registry'
      unset DOTFILES_FAILURE_REGISTRY
      When call display_failure_summary
      The status should be success
    End

    It 'displays summary for failures'
      create_sample_failure "yazi" "https://example.com/yazi.zip" "v1.0" "Download failed"
      When call display_failure_summary
      The output should include "Installation Summary"
      The output should include "yazi - Manual Installation Required"
      The stderr should include "Some installations failed"
    End

    It 'displays multiple failures'
      create_sample_failure "yazi" "https://example.com/yazi.zip" "v1.0" "Download failed"
      create_sample_failure "glow" "https://example.com/glow.tar.gz" "v1.5" "Network timeout"
      When call display_failure_summary
      The output should include "yazi - Manual Installation Required"
      The output should include "glow - Manual Installation Required"
      The stderr should include "Some installations failed"
    End
  End
End
