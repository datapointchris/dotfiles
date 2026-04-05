# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

#@lsalias
#--> List all aliases
function lsalias() {
  echo

  local aliases_file="$SHELL_DIR/aliases.sh"

  # Process aliases from the single generated file
  local message=""
  if [[ -f "$aliases_file" ]]; then
    message="$(grep '^alias ' "$aliases_file" | sed 's/alias//g' | sed 's/=/Ø/')"
  fi

  # Function to format and display aliases
  format_aliases() {
    local msg="$1"
    local filter="$2"

    if [[ -n "$msg" ]]; then
      if [[ -n "$filter" ]]; then
        command echo -E "$msg" | grep -i "$filter" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
      else
        command echo -E "$msg" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
      fi
    fi
  }

  if [[ -n "$message" ]]; then
    color_green "$(print_section "Aliases")"
    format_aliases "$message" "$1"
    echo
  fi

  if [[ -z "$message" ]]; then
    color_yellow "No aliases found"
  fi
}

#@lsfunc
#--> List all functions
function lsfunc() {
  echo ""

  local functions_file="$SHELL_DIR/functions.sh"

  # Process functions from the single generated file
  local message=""
  if [[ -f "$functions_file" ]]; then
    message="$("shelldocsparser" "$functions_file")"
  fi

  # Function to format and display functions
  format_functions() {
    local msg="$1"
    local filter="$2"

    if [[ -n "$msg" ]]; then
      if [[ -n "$filter" ]]; then
        command echo "$msg" | grep -i "$filter" | sort | column -t -s \|
      else
        command echo "$msg" | sort | column -t -s \|
      fi
    fi
  }

  if [[ -n "$message" ]]; then
    color_green "$(print_section "Functions")"
    format_functions "$message" "$1"
    echo
  fi

  if [[ -z "$message" ]]; then
    color_yellow "No functions found"
  fi
}

#@commithelp
#--> Suggest commit type based on staged files
function commithelp() {
  echo ""
  color_green "$(print_section "Commit Type Suggestions")"
  echo ""

  # Get staged files
  local staged_files
  staged_files=$(git diff --cached --name-only 2>/dev/null)

  if [ -z "$staged_files" ]; then
    color_yellow "No files staged for commit"
    echo "Use 'git add <files>' to stage changes first"
    echo ""
    return 1
  fi

  # Show staged files
  color_blue "Staged files:"
  echo "$staged_files" | while read -r file; do
    echo "  - $file"
  done
  echo ""

  # Analyze patterns and suggest commit types
  local suggestions=()
  # shellcheck disable=SC2034  # confidence reserved for future use
  local confidence=""

  # Check for dependency files (high confidence)
  if echo "$staged_files" | grep -qE '(package\.json|package-lock\.json|requirements\.txt|Pipfile\.lock|go\.mod|go\.sum|Gemfile\.lock|composer\.lock|yarn\.lock|pnpm-lock\.yaml|uv\.lock)$'; then
    suggestions+=("$(color_green "✓") $(color_blue "deps:") Update package versions")
    confidence="high"
  fi

  # Check for lock files only (very high confidence for deps)
  if echo "$staged_files" | grep -qE '(package-lock\.json|Pipfile\.lock|go\.sum|Gemfile\.lock|yarn\.lock|pnpm-lock\.yaml|uv\.lock)$'; then
    if [ ${#suggestions[@]} -eq 0 ]; then
      suggestions+=("$(color_green "✓✓") $(color_blue "deps:") Lock file updates (very likely)")
      # shellcheck disable=SC2034
      confidence="very-high"
    fi
  fi

  # Check for CI/CD and infrastructure files
  if echo "$staged_files" | grep -qE '(\.github/workflows/|Dockerfile|docker-compose|terraform/|\.tf$|kubernetes/|k8s/|\.yml$|\.yaml$)'; then
    suggestions+=("$(color_green "✓") $(color_blue "ops:") Infrastructure/CI-CD changes")
  fi

  # Check for build configuration
  if echo "$staged_files" | grep -qE '(webpack\.config|vite\.config|rollup\.config|tsconfig\.json|babel\.config|\.babelrc|Makefile|CMakeLists\.txt|build\.gradle|pom\.xml)'; then
    suggestions+=("$(color_green "✓") $(color_blue "build:") Build system configuration")
  fi

  # Check for test files
  if echo "$staged_files" | grep -qE '(test_|_test\.|\.test\.|\.spec\.|tests?/|__tests__/)'; then
    suggestions+=("$(color_green "✓") $(color_blue "test:") Test changes")
  fi

  # Check for documentation
  if echo "$staged_files" | grep -qE '(README|CHANGELOG|\.md$|docs?/|LICENSE)'; then
    suggestions+=("$(color_green "✓") $(color_blue "docs:") Documentation")
  fi

  # Check for gitignore and common chore files
  if echo "$staged_files" | grep -qE '(\.gitignore|\.editorconfig|\.nvmrc|\.python-version)'; then
    suggestions+=("$(color_green "✓") $(color_blue "chore:") Configuration/maintenance")
  fi

  # Check for formatting config files
  if echo "$staged_files" | grep -qE '(\.prettierrc|\.eslintrc|\.pylintrc|\.flake8|\.black|pyproject\.toml|\.editorconfig)'; then
    # If only config files, it's chore; if code files too, it might be style
    local code_files
    code_files=$(echo "$staged_files" | grep -vE '\.(json|yaml|yml|toml|ini|cfg|rc)$')
    if [ -z "$code_files" ]; then
      suggestions+=("$(color_green "✓") $(color_blue "chore:") Formatting configuration")
    else
      suggestions+=("$(color_yellow "?") $(color_blue "style:") If you ran a formatter (prettier/eslint/black)")
    fi
  fi

  # Check file extensions for code vs docs vs config
  local has_code=false
  # shellcheck disable=SC2034  # has_docs/has_config reserved for future use
  local has_docs=false
  local has_config=false

  if echo "$staged_files" | grep -qE '\.(js|ts|py|go|rs|java|cpp|c|rb|php|swift|kt|sh|bash|zsh)$'; then
    has_code=true
  fi

  if echo "$staged_files" | grep -qE '\.(md|txt|rst|adoc)$'; then
    # shellcheck disable=SC2034
    has_docs=true
  fi

  if echo "$staged_files" | grep -qE '\.(json|yaml|yml|toml|ini|cfg)$'; then
    # shellcheck disable=SC2034
    has_config=true
  fi

  # General suggestions based on file types
  if [ "$has_code" = true ]; then
    suggestions+=("$(color_yellow "?") $(color_blue "feat:") If adding new functionality")
    suggestions+=("$(color_yellow "?") $(color_blue "fix:") If fixing a bug")
    suggestions+=("$(color_yellow "?") $(color_blue "refactor:") If restructuring without behavior change")
    suggestions+=("$(color_yellow "?") $(color_blue "perf:") If improving performance")
  fi

  # Display suggestions
  if [ ${#suggestions[@]} -gt 0 ]; then
    color_yellow "Suggested commit types:"
    printf '%s\n' "${suggestions[@]}"
  else
    color_yellow "No specific suggestions based on file patterns"
    echo "Review 'lscommits' for all commit types"
  fi

  echo ""
  color_bright_black "Legend:"
  echo "  $(color_green "✓✓") Very high confidence"
  echo "  $(color_green "✓")  High confidence based on file patterns"
  echo "  $(color_yellow "?")  Possible - depends on your changes"
  echo ""
  color_bright_black "Tip: Use 'workflows show git-conventional-commits' for full list"
  echo ""
}
