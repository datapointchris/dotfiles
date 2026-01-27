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

#@lscommits
#--> List conventional commits
function lscommits() {
  echo ""
  color_green "$(print_section "Conventional Commits")"
  local message
  message=$(
    cat <<-EOF
			$(color_blue "feat: |${normal} New feature or functionality")
			$(color_blue "fix: |${normal} Bug fixes")
			$(color_blue "perf: |${normal} Performance improvements")
			$(color_blue "refactor: |${normal} Code restructuring without behavior change")
			$(color_blue "style: |${normal} Code formatting/linting (prettier, eslint, black)")
			$(color_blue "test: |${normal} Add or modify tests")
			$(color_blue "docs: |${normal} Documentation changes")
			$(color_blue "typo: |${normal} Fix typos and spelling")
			$(color_blue "deps: |${normal} Update package versions (npm, pip, etc.)")
			$(color_blue "build: |${normal} Build system config (webpack, tsconfig, Makefile)")
			$(color_blue "ops: |${normal} Infrastructure (terraform, k8s, CI/CD, docker)")
			$(color_blue "chore: |${normal} Maintenance (.gitignore, move files, scripts)")
			$(color_blue "revert: |${normal} Revert a previous commit")
		EOF
  )
  echo "$message" | column -t -s \|
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
  color_bright_black "Tip: Use 'lscommits' for full list or 'lscommits -d' for detailed examples"
  echo ""
}

#@lsterm
#--> Display terminal information, such as commands and workflows
function lsterm() {
  echo
  print_title "Terminal Commands"

  # -------------------- ripgrep -------------------- #

  local ripgrep_commands
  ripgrep_commands=$(
    cat <<-EOF
			  $(color_bright_black "rg foo |${normal} => foo in current directory")
			  $(color_bright_black "rg foo bar |${normal} => foo and bar in current directory")
			  $(color_bright_black "rg -t py foo bar |${normal} => foo and bar in python files")
			  $(color_bright_black "rg fast README.md |${normal} => fast in README.md")
			  $(color_bright_black "rg 'fast\w+' README.md |${normal} => fast followed by one or more word like characters in README.md")
			  $(color_bright_black "rg 'fn write\(' |${normal} => 'fn write(' in all files")
		EOF
  )

  color_green "ripgrep"
  echo "  ripgrep is a line-oriented search tool that recursively searches your current directory for a regex pattern."
  echo
  echo "$ripgrep_commands" | column -t -s \|
  echo
  color_bright_red "  Tutorial"
  echo "  https://codapi.org/try/ripgrep/"
  echo
  echo

  # -------------------- fzf -------------------- #

  local fzf_commands
  fzf_commands=$(
    cat <<-EOF
			  $(color_bright_black "-- Token --|-- Match type --|-- Description --")
			  $(color_bright_black "sbtrkt |${normal} fuzzy-match |${normal} match sbtrkt")
			  $(color_bright_black "'wild |${normal} exact-match (quoted) |${normal} include wild")
			  $(color_bright_black "'wild' |${normal} exact-boundary-match (quoted both ends) |${normal} include wild at word boundaries")
			  $(color_bright_black "^music |${normal} prefix-exact-match |${normal} start with music")
			  $(color_bright_black ".mp3$ |${normal} suffix-exact-match |${normal} end with .mp3")
			  $(color_bright_black "!fire |${normal} inverse-exact-match |${normal} do not include fire")
			  $(color_bright_black "!^music |${normal} inverse-prefix-exact-match |${normal} do not start with music")
			  $(color_bright_black "!.mp3$ |${normal} inverse-suffix-exact-match |${normal} do not end with .mp3")
		EOF
  )
  local fzf_special
  fzf_special=$(
    cat <<-EOF
			  $(color_bright_black "nvim -o \`fzf\` |${normal} open neovim with files selected by fzf")
			  $(color_bright_black "Ctrl + R |${normal} search history of commands (enabled by fzf)")
		EOF
  )

  color_green "fzf"
  echo "  fzf is a general-purpose command-line fuzzy finder."
  echo
  color_blue "  Search Syntax"
  echo "  Unless otherwise specified, fzf starts in "extended-search mode" where you can type in"
  echo "  multiple search terms delimited by spaces."
  echo "  e.g. ^music .mp3$ sbtrkt !fire"
  echo
  echo "$fzf_commands" | column -t -s \|
  echo
  color_blue "  Special Commands"
  echo
  echo "$fzf_special" | column -t -s \|
  echo
  echo

  # -------------------- zoxide -------------------- #

  local zoxide_commands
  zoxide_commands=$(
    cat <<-EOF
			  $(color_bright_black "cd foo |${normal} cd into highest ranked directory matching foo")
			  $(color_bright_black "cd foo bar |${normal} cd into highest ranked directory matching foo and bar")
			  $(color_bright_black "cd foo / |${normal} cd into a subdirectory starting with foo")

			  $(color_bright_black "cd ~/foo |${normal} z also works like a regular cd command")
			  $(color_bright_black "cd foo/ |${normal} cd into relative path")
			  $(color_bright_black "cd .. |${normal} cd one level up")
			  $(color_bright_black "cd - |${normal} cd into previous directory")

			  $(color_bright_black "cdi foo |${normal} cd with interactive selection (using fzf)")

			  $(color_bright_black "cd foo<SPACE><TAB> |${normal} show interactive completions")
		EOF
  )

  color_green "zoxide"
  echo "  zoxide remembers your most used directories and allows you to jump to them with ease."
  color_yellow "  Note: ${normal}z is aliased to 'cd' in .zshrc"
  echo
  echo "$zoxide_commands" | column -t -s \|
  echo
  echo

  # -------------------- watch -------------------- #

  color_green "watch"
  echo "  watch is used to execute a program periodically, showing output in full screen."
  echo
  color_bright_black "  tldr watch |${normal} for more information"
  echo
  echo

  # -------------------- eza -------------------- #

  color_green "eza"
  echo "  eza is a replacement for 'ls' command"
  echo "  after multiple reviews, it is not worth the install and configuration at this time"
  echo "  a combination of tmux and neovim provides a better workflow"
  echo
  echo
}

#@lsneovim
#--> List neovim commands
function lsneovim() {
  echo ""
  color_green "$(print_section "Vim / Neovim Commands")"
  local message
  message=$(
    cat <<-EOF
		  $(color_green "Functionality")
        $(color_blue "w |${normal} start of next word, EXCLUDING its first character")
        $(color_blue "e |${normal} end of the current word, INCLUDING the last character")
        $(color_blue "$ |${normal} to the end of the line, INCLUDING the last character")
        $(color_blue "0 |${normal} to the beginning of the line")
        $(color_blue "^ |${normal} to the first non-blank character of the line")
        $(color_blue "gg |${normal} to the top of file")
        $(color_blue "G |${normal} to the bottom of file")
        $(color_blue "H |${normal} to the top of the screen")
        $(color_blue "M |${normal} to the middle of the screen")
        $(color_blue "L |${normal} to the bottom of the screen")

      $(color_green "Basic Movement")
        $(color_blue "Ctrl + u |${normal} Move half page up")
        $(color_blue "Ctrl + d |${normal} Move half page down")
        $(color_blue "Ctrl + b |${normal} Move full page up")
        $(color_blue "Ctrl + f |${normal} Move full page down")
        $(color_blue "Ctrl + y |${normal} Move screen up")
        $(color_blue "Ctrl + e |${normal} Move screen down")

      $(color_green "Editing")
        $(color_blue "i |${normal} Insert mode before cursor")
        $(color_blue "I |${normal} Insert mode at beginning of line")
        $(color_blue "a |${normal} Insert mode after cursor")
        $(color_blue "A |${normal} Insert mode at end of line")
        $(color_blue "o |${normal} Insert line below")
        $(color_blue "O |${normal} Insert line above")
        $(color_blue "r |${normal} Replace character")
        $(color_blue "R |${normal} Replace mode")
        $(color_blue "x |${normal} Delete character")
        $(color_blue "X |${normal} Delete character before cursor")
        $(color_blue "dd |${normal} Delete line")
        $(color_blue "yy |${normal} Yank line")
        $(color_blue "p |${normal} Paste after cursor")
        $(color_blue "P |${normal} Paste before cursor")
        $(color_blue "u |${normal} Undo")
        $(color_blue "Ctrl + r |${normal} Redo")
        $(color_blue ". |${normal} Repeat last command")

      $(color_green "Nouns")
        $(color_blue "w |${normal} Word")
        $(color_blue "s |${normal} Sentence")
        $(color_blue "p |${normal} Paragraph")
        $(color_blue "t |${normal} Tag")
        $(color_blue "b |${normal} Block")

      $(color_green "Verbs")
        $(color_blue "d |${normal} Delete")
        $(color_blue "c |${normal} Change")
        $(color_blue "y |${normal} Yank (copy)")
        $(color_blue "v |${normal} Visual (select)")
        $(color_blue "p |${normal} Put (paste)")

      $(color_green "Modifiers")
        $(color_blue "i |${normal} Inner")
        $(color_blue "a |${normal} Around")
        $(color_blue "t |${normal} Till")
        $(color_blue "f |${normal} Find")

      $(color_green "Combinations")
        $(color_blue "ciw |${normal} Change inner word")
        $(color_blue "cit |${normal} Change inner tag")
        $(color_blue "cip |${normal} Change inner paragraph")
        $(color_blue "ci( |${normal} Change inner parentheses")
        $(color_blue "ci\" |${normal} Change inner quotes")
        $(color_blue "ci{ |${normal} Change inner curly braces")

      $(color_green "Search and Replace")
        $(color_blue "/pattern |${normal} Search forward for pattern")
        $(color_blue "?pattern |${normal} Search backward for pattern")
        $(color_blue "n |${normal} Repeat search in same direction")
        $(color_blue "N |${normal} Repeat search in opposite direction")
        $(color_blue ":s/foo/bar/g |${normal} Replace foo with bar in current line")
        $(color_blue ":%s/foo/bar/g |${normal} Replace foo with bar in entire file")
        $(color_blue ":s/foo/bar/gc |${normal} Replace foo with bar in current line with confirmation")
        $(color_blue ":%s/foo/bar/gc |${normal} Replace foo with bar in entire file with confirmation")
        $(color_blue ":set ic |${normal} Ignore case in search")
        $(color_blue ":set is |${normal} Enable partial search")
        $(color_blue ":set hls |${normal} Enable search highlight")
        $(color_blue ":noh |${normal} Remove search highlight")

      $(color_green "Buffers")
        $(color_blue ":e file |${normal} Edit file")
        $(color_blue ":ls |${normal} List buffers")
        $(color_blue ":bnext |${normal} Next buffer")
        $(color_blue ":bprev |${normal} Previous buffer")
        $(color_blue ":bfirst |${normal} First buffer")
        $(color_blue ":blast |${normal} Last buffer")
        $(color_blue ":bdelete |${normal} Delete buffer")
        $(color_blue ":bdelete 2 |${normal} Delete buffer 2")
        $(color_blue ":bdelete foo |${normal} Delete buffer with foo in name")
        $(color_blue ":bdelete foo bar |${normal} Delete buffer with foo or bar in name")

      $(color_green "Windows")
        $(color_blue ":sp |${normal} Split window horizontally")
        $(color_blue ":vsp |${normal} Split window vertically")
        $(color_blue ":q |${normal} Quit window")
        $(color_blue ":q! |${normal} Quit window without saving")
        $(color_blue ":w |${normal} Save file")
        $(color_blue ":wq |${normal} Save file and quit")
        $(color_blue ":e |${normal} Edit file")
        $(color_blue ":e! |${normal} Edit file without saving")

      $(color_green "Tabs")
        $(color_blue ":tabnew |${normal} Open new tab")
        $(color_blue ":tabnext |${normal} Next tab")
        $(color_blue ":tabprev |${normal} Previous tab")
        $(color_blue ":tabclose |${normal} Close tab")
        $(color_blue ":tabonly |${normal} Close all tabs except current")

      $(color_green "Help")
        $(color_blue ":help |${normal} Open help")
        $(color_blue ":help w |${normal} Open help for w command")
        $(color_blue ":helpgrep foo |${normal} Search help for foo")
        $(color_blue ":helptags |${normal} Generate help tags")
        $(color_blue ":helptags ALL |${normal} Generate help tags for all directories")

		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}

#@lstmux
#--> List tmux commands
function lstmux() {
  echo ""
  color_green "$(print_section "TMUX Commands")"
  local message
  message=$(
    cat <<-EOF
			$(color_green "Menu")
			  $(color_blue "Open Menu: |${normal} pre + space")
			  $(color_blue "Show Keybindings Popup: |${normal} pre + C-p")
			$(color_green "Windows")
			  $(color_blue "New Window: |${normal} pre + c")
			  $(color_blue "Select Window: |${normal} pre + 1-9, starts at 1")
			  $(color_blue "Rename Window: |${normal} pre + ,")
			  $(color_blue "Previous Window: |${normal} pre + p")
			  $(color_blue "Next Window: |${normal} pre + n")
			  $(color_blue "Close Window: |${normal} pre + k")
			  $(color_blue "Last Active Window: |${normal} pre + l")
			$(color_green "Panes")
			  $(color_blue "Split Horizontally: |${normal} pre + {pipe}")
			  $(color_blue "Split Vertically: |${normal} pre + -")
			  $(color_blue "Rename Pane: |${normal} tmux select-pane -T 'New name'")
			  $(color_blue "Navigate panes: |${normal} Ctrl + hjkl")
			  $(color_blue "Navigate panes: |${normal} pre + LRUD")
			  $(color_blue "Resize pane: |${normal} pre + Ctrl-Option-hjkl")
			  $(color_blue "Resize pane: |${normal} pre + Cmd-Option-LRUD")
			  $(color_blue "Toggle last active pane: |${normal} pre + ;")
			  $(color_blue "Zoom In on pane: |${normal} pre + z")
			  $(color_blue "Close Pane: |${normal} pre + x")
			  $(color_blue "Swap with Next Pane: |${normal} pre + }")
			  $(color_blue "Swap with Previous Pane: |${normal} pre + {")
			  $(color_blue "Breakout Pane to New Window: |${normal} pre + !")
			$(color_green "Sessions")
			  $(color_blue "Rename Current Session: |${normal} pre + $")
			  $(color_blue "Detach Session: |${normal} pre + d")
			  $(color_blue "List Sessions: |${normal} tmux ls")
			  $(color_blue "New Session: |${normal} tmux new -s session_name")
			  $(color_blue "Attach Session: |${normal} tmux attach -t session_name")
			  $(color_blue "Switch Session: |${normal} tmux switch -t session_name")
			  $(color_blue "Detach from Session: |${normal} tmux detach")
			$(color_green "Copy Mode")
			  $(color_blue "Enter Copy Mode: |${normal} pre + Enter")
			  $(color_blue "Scroll Up: |${normal} pre + PageUp")
			  $(color_blue "Scroll Down: |${normal} pre + PageDown")
			  $(color_blue "Copy Selection: |${normal} pre + w")
			  $(color_blue "Exit Copy Mode: |${normal} leq")
			$(color_green "General")
			  $(color_green "pre: |${normal} ctrl + <space>")
			  $(color_blue "Command Mode: |${normal} pre + :")
			  $(color_blue "Copy Mode: |${normal} pre + Enter")
			  $(color_blue "Universal Menu: |${normal} pre + m")
			  $(color_blue "Copy current command to clipboard: |${normal} pre + y")
			  $(color_blue "Copy current directory to clipboard: |${normal} pre + Y")
			  $(color_blue "Save Tmux Environment: |${normal} pre + Ctrl-s")
			  $(color_blue "Restore Tmux Environment: |${normal} pre + Ctrl-r")
			  $(color_blue "Reload tmux conf file: |${normal} 'tmux source-file ~/.tmux.conf'")
			$(color_green "Tree Sidebar")
			  $(color_blue "Toggle Tree Sidebar: |${normal} pre + <tab>")
			  $(color_blue "Toggle Tree Sidebar with Focus: |${normal} pre + <backspace>")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}

#@lsnano
#--> List nano commands
function lsnano() {
  echo ""
  color_green "$(print_section "Nano Commands")"
  local message
  message=$(
    cat <<-EOF
			$(color_green "File handling")
			  $(color_blue "Ctrl+S |${normal} Save current file")
			  $(color_blue "Ctrl+O |${normal} Offer to write file ("Save as")")
			  $(color_blue "Ctrl+R |${normal} Insert a file into current one")
			  $(color_blue "Ctrl+X |${normal} Close buffer, exit from nano")
			$(color_green "Editing")
			  $(color_blue "Ctrl+K |${normal} Cut current line into cutbuffer")
			  $(color_blue "Alt+6 |${normal} Copy current line into cutbuffer")
			  $(color_blue "Ctrl+U |${normal} Paste contents of cutbuffer")
			  $(color_blue "Alt+T |${normal} Cut until end of buffer")
			  $(color_blue "Ctrl+] |${normal} Complete current word")
			  $(color_blue "Alt+3 |${normal} Comment/uncomment line/region")
			  $(color_blue "Alt+U |${normal} Undo last action")
			  $(color_blue "Alt+E |${normal} Redo last undone action")
			$(color_green "Search and replace")
			  $(color_blue "Ctrl+Q |${normal} Start backward search")
			  $(color_blue "Ctrl+W |${normal} Start forward search")
			  $(color_blue "Alt+Q |${normal} Find next occurrence backward")
			  $(color_blue "Alt+W |${normal} Find next occurrence forward")
			  $(color_blue "Alt+R |${normal} Start a replacing session")
			$(color_green "Deletion")
			  $(color_blue "Ctrl+H |${normal} Delete character before cursor      ")
			  $(color_blue "Ctrl+D |${normal} Delete character under cursor")
			  $(color_blue "Alt+Bsp |${normal} Delete word to the left")
			  $(color_blue "Ctrl+Del |${normal} Delete word to the right")
			  $(color_blue "Alt+Del |${normal} Delete current line")
			$(color_green "Operations")
			  $(color_blue "Ctrl+T |${normal} Execute some command")
			  $(color_blue "Ctrl+J |${normal} Justify paragraph or region")
			  $(color_blue "Alt+J |${normal} Justify entire buffer")
			  $(color_blue "Alt+B |${normal} Run a syntax check")
			  $(color_blue "Alt+F |${normal} Run a formatter/fixer/arranger")
			  $(color_blue "Alt+: |${normal} Start/stop recording of macro")
			  $(color_blue "Alt+; |${normal} Replay macro")
			$(color_green "Moving around")
			  $(color_blue "Ctrl+B |${normal} One character backward")
			  $(color_blue "Ctrl+F |${normal} One character forward")
			  $(color_blue "Ctrl+← |${normal} One word backward")
			  $(color_blue "Ctrl+→ |${normal} One word forward")
			  $(color_blue "Ctrl+A |${normal} To start of line")
			  $(color_blue "Ctrl+E |${normal} To end of line")
			  $(color_blue "Ctrl+P |${normal} One line up")
			  $(color_blue "Ctrl+N |${normal} One line down")
			  $(color_blue "Ctrl+↑ |${normal} To previous block")
			  $(color_blue "Ctrl+↓ |${normal} To next block")
			  $(color_blue "Ctrl+Y |${normal} One page up")
			  $(color_blue "Ctrl+V |${normal} One page down")
			  $(color_blue "Alt+\ |${normal} To top of buffer")
			  $(color_blue "Alt+/ |${normal} To end of buffer")
			$(color_green "Special movement")
			  $(color_blue "Alt+G |${normal} Go to specified line")
			  $(color_blue "Alt+] |${normal} Go to complementary bracket")
			  $(color_blue "Alt+↑ |${normal} Scroll viewport up")
			  $(color_blue "Alt+↓ |${normal} Scroll viewport down")
			  $(color_blue "Alt+< |${normal} Switch to preceding buffer")
			  $(color_blue "Alt+> |${normal} Switch to succeeding buffer")
			$(color_green "Information")
			  $(color_blue "Ctrl+C |${normal} Report cursor position")
			  $(color_blue "Alt+D |${normal} Report line/word/character count")
			  $(color_blue "Ctrl+G |${normal} Display help text")
			$(color_green "Various")
			  $(color_blue "Alt+A |${normal} Turn the mark on/off")
			  $(color_blue "Tab |${normal} Indent region")
			  $(color_blue "Shift+Tab |${normal} marked region")
			  $(color_blue "Alt+V |${normal} Enter next keystroke verbatim")
			  $(color_blue "Alt+N |${normal} Turn line numbers on/off")
			  $(color_blue "Alt+P |${normal} Turn visible whitespace on/off")
			  $(color_blue "Alt+X |${normal} Hide or unhide the help lines")
			  $(color_blue "Ctrl+L |${normal} Refresh the screen")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}
