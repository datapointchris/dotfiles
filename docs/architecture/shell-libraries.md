# Shell Libraries Architecture

System-wide shell libraries in `configs/common/.local/shell/`, deployed to
`~/.local/shell/`. Each serves a distinct purpose and can be used alone or
combined. The roster is
`rg -o '^[a-z_][a-z0-9_]*\(\)' configs/common/.local/shell/*.sh` — this page
explains the ones with a design decision behind them rather than listing every
function, because a hand-copied roster drifts and this one had.

## Sourcing Rules

A library loaded with `source` runs in the caller's shell, so any option it sets
(`set -euo pipefail`, `shopt`) persists in the calling script. Libraries must
therefore never touch shell options — only the script decides its own error
handling. A library contains function definitions, variable assignments and
conditional logic, and nothing else.

`error-handling.sh` follows this by exposing `enable_error_traps` as an explicit
opt-in rather than setting strict mode on load — the name is the only trap in it. Every library is checked for the
violation by `tests/shell/test_shell_libraries.py`; see
[Library Flag Pollution](../learnings/library-flag-pollution.md) for the
incident that produced the test.

## Library Overview

### logging.sh - Status Messages with Log Prefixes

**Location**: `~/.local/shell/logging.sh`
**Purpose**: Core logging for scripts that output status messages and may be logged/monitored

**When to use**:

- Scripts run unattended or in CI/CD
- Installation/update scripts that need logging
- Any script whose output might be piped to log files
- Scripts that need parseable output for tools like logsift

**Functions**: `rg -o '^[a-z_][a-z0-9_]*\(\)' configs/common/.local/shell/logging.sh`

**Output format**: every one of them emits a `[LEVEL]` prefix a log parser can key
on, ahead of the color and the unicode icon a human reads. That prefix is the
whole difference from `formatting.sh` below, and it is why a script that might be
piped to a log file writes here instead.

Two contracts the names do not carry. **Everything goes to stderr**, success and
info included, so a script's stdout stays whatever the script is actually
producing. And `log_fatal` and `die` exit 1 rather than returning, which makes
either one unusable inside a command substitution or a pipeline the caller means
to survive.

**Example**:

```bash
#!/usr/bin/env bash
source "$HOME/.local/shell/logging.sh"

log_info "Starting backup process..."
log_success "Backed up 156 files"
log_warning "Skipped 3 files (permissions denied)"
log_error "Failed to backup config.yml" "$BASH_SOURCE" "$LINENO"
```

### formatting.sh - Visual Structure for Interactive Output

**Location**: `~/.local/shell/formatting.sh`
**Purpose**: Visual formatting for interactive scripts with headers, sections, banners

**When to use**:

- Interactive scripts run by humans at terminal
- Scripts with visual sections/phases
- Menu systems and interactive tools
- Scripts that prioritize visual appeal over parseability

**Functions**: `rg -o '^[a-z_][a-z0-9_]*\(\)' configs/common/.local/shell/formatting.sh`

Four families come out of that command, and the shape is what makes them
predictable rather than the individual names. The **structural** ones take
`(text, [color])` and draw a rule around it — a thick border, a thin underline,
double bars, a centered full-width line — and each carries `_success`, `_error`,
`_warning` and `_info` variants that add an emoji. The **status** ones take a
message and prefix an icon, using the same icons as `logging.sh` and
deliberately omitting the `[LEVEL]` prefix; picking between the two libraries is
picking whether the output will be parsed. The **help** ones are the grammar
below. The rest are separators, colour helpers, a `has_command` test, a
`center_text` that pads to `tput cols`, and a `formatting_demo` that prints a
sample of the whole library.

**Help Screen Grammar**: `help_header`, `help_usage`, `help_section`, `help_row`,
`help_text`, `help_end` — a closed set, listed here because it is a spec rather
than a roster.

Build every `usage()` / `show_help()` from these and nothing else. One `help_row` per line, in the
order it prints, so the source shows the shape of the screen:

```bash
show_help() {
  help_header "menu" "A pointer across your collections."
  help_usage  "menu [find|search] <term>"

  help_section "Commands"
  help_row "menu find"  "<term>"  "Search (Enter opens the full view)"
  help_row "menu help"  ""        "Show this help"

  help_end
}
```

No call site passes a width or a colour, and none should:

- **Widths are computed.** `help_row` buffers; the flush sizes the description column from the
  longest row in the section. A row that outgrows its neighbours re-flows the section instead of
  overrunning it, which is how the alignment drift in these screens kept happening.
- **Colours come from the section name.** Commands/Verbs/Suites/Groups/Phases are bright cyan,
  Options/Flags/Arguments/Environment Variables bright magenta, Examples bright yellow.
  App-specific headings rotate through the rest of the palette by position, so adjacent sections
  always differ.
- **Blank lines belong to the library.** `help_section` emits its own leading blank — never write
  `echo ""` around one.

Two rules follow from the buffer: close a screen with `help_end`, and use `help_text` rather than a
bare `echo` for prose between rows, so pending rows flush ahead of it.

The `pytermstyle` package mirrors all six functions for the Python apps, and `gotermstyle` does the
same for the Go CLIs; all three render byte-identical screens. `pytermstyle` was extracted from this
repo in August 2026 — it lived here as `appcore/formatting.py` for as long as every consumer was a
script in `apps/`, and left when one stopped being: `safekeep` moved to its own repo and could
not take the help grammar with it through a `sys.path` hack. A consumer declares `pytermstyle` in
its PEP 723 header, resolved from a git tag; nothing left in this repo's `apps/` does, because the
Python scripts still here are stdlib-only. The packaged Python CLIs use Typer and get their help
from Rich instead.

The underlying `print_help_row(width, name, [description], [color])` and
`print_example_row(width, command, [comment])` remain available for a one-off row outside a help
screen. They emit the colour escape *outside* the padded field — `printf` counts escape bytes
toward a field width — and *before* the two-space indent, so the indent stays contiguous with the
name for anything grepping the output for it.

**Example**:

```bash
#!/usr/bin/env bash
source "$HOME/.local/shell/formatting.sh"

print_header "Backup Tool" "blue"
print_section "Phase 1: Scanning"

# Visual-only script - no logging needed
for file in *.txt; do
  print_success "Scanned: $file"
done

print_header_success "Backup Complete"
```

### flags.sh - Feature Flag Tests

**Location**: `~/.local/shell/flags.sh`
**Purpose**: One truthy test for every on/off switch, so a flag reads the same from `.zshrc`, an installer, or an app
**Dependencies**: None — deliberately, so it can load before colors and formatting do

**When to use**:

- Any code that asks whether a feature is wanted on this machine
- Never for whether a tool is *installed* — that stays a `command -v` check

**Functions**: `rg -o '^[a-z_][a-z0-9_]*\(\)' configs/common/.local/shell/flags.sh`

`flag_enabled NAME [default]` is the one every caller wants: true when `$NAME` is truthy, with
`default` applying when the variable is unset, empty, or holds an unrecognized value, and itself
defaulting to enabled. `flag_classify` is the finer-grained sibling — 0 on, 1 off, 2 unrecognized —
and exists because `dotfiles check` has to report a typo as *something wrong* rather than as
something `apply` can fix.

Truthy is `1`/`true`/`yes`/`on` and falsey is `0`/`false`/`no`/`off`, each case-insensitive.

Unset means *enabled* because the model is load-everywhere-flag-decides: a machine whose `~/.env` predates a flag keeps the feature rather than silently losing it. Anything that should start life off passes an explicit `0`.

**Example**:

```bash
source "$HOME/.local/shell/flags.sh"

flag_enabled SHELL_NUDGE && cache_eval -b doit doit-nudge doit shell init zsh
flag_enabled ZSHRC_DEBUG 0 && print_startup_timings
```

The flag list and its per-machine defaults live in `install/flags.yml`; this library only answers the question.

### error-handling.sh - Robust Error Management

**Location**: `~/.local/shell/error-handling.sh`
**Purpose**: Cleanup registration, verification helpers, and download retry
**Dependencies**: Sources logging.sh

**When to use**:

- Scripts that create temporary files/directories
- Download/installation scripts needing retry logic
- Scripts that must undo their own mess on the way out

**Functions**: `rg -o '^[a-z_][a-z0-9_]*\(\)' configs/common/.local/shell/error-handling.sh`

Three things those names do not carry. `enable_error_traps` installs no handler — its whole body is
`set -euo pipefail`, run in the caller's shell — so the cleanup a script registers runs only if that
script also writes `trap run_cleanup EXIT`, which is the line the library's own usage block at the
foot of the file shows. The `verify_*` and `require_*` helpers are fatal rather than falsy — they
call `log_fatal`, so a caller cannot branch on the result. And `download_file_with_retry` is the only
thing here that retries, for the reason in
[Why Downloads Retry but Scripts Do Not](#why-downloads-retry-but-scripts-do-not).

**Example**:

```bash
#!/usr/bin/env bash
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/error-handling.sh"
enable_error_traps

# Register cleanup
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"
trap run_cleanup EXIT

# Verify prerequisites
require_commands curl tar jq

# Download with retry
download_file_with_retry \
  "https://example.com/package.tar.gz" \
  "$TMP_DIR/package.tar.gz" \
  "Package archive" \
  3

# Verify and install
verify_file "$TMP_DIR/package.tar.gz" "Downloaded package"
safe_move "$TMP_DIR/binary" "$HOME/.local/bin/binary" "Binary"

exit_success
```

## Sourcing Patterns

### From Scripts in Repo (use DOTFILES_DIR)

```bash
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
```

### From Scripts After Installation (use SHELL_DIR or HOME)

```bash
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/logging.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/error-handling.sh"
```

### From Interactive Shell (already sourced in .zshrc)

Functions are available directly in interactive shells - no need to source.

## Why Downloads Retry but Scripts Do Not

`download_file_with_retry` is the one retrying thing in the libraries, and it is
deliberately scoped to a single `curl`: three attempts, a fixed two-second gap,
then `log_fatal`. No exponential backoff, and nothing above it retries.

An installer that fails usually fails persistently — a blocked host, a moved
release asset, a missing dependency — so retrying the *script* spends minutes
re-running work that will fail the same way, and buries the error under repeated
output. A single download is the one case where the failure is plausibly
transient and the retry is cheap. Everything coarser fails fast and gets re-run
by hand, which the idempotent design makes safe. `dotfiles apply` isolates
failures between installers rather than retrying them; see
[Resilient Installation Patterns](../learnings/resilient-installation-patterns.md).

## See Also

- `configs/common/.local/shell/colors.sh` - The `color_*` helpers and `color_enabled`, used by formatting.sh
- `install/flags.yml` - The declared flag list and per-machine defaults `flags.sh` tests
- [Symlinks Manager](../reference/tools/symlinks.md) - Symlinks manager documentation
