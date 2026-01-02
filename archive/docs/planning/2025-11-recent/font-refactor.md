# Font Tool Refactoring Plan

## Executive Summary

Streamline the font tool by removing manual file editing, simplifying commands, and implementing automatic tracking with cross-platform merge support using JSONL storage.

## Current Problems

1. **Manual file editing** - favorites list is hardcoded in script
2. **Overlapping concepts** - test, like/dislike, notes, favorites all doing similar things
3. **Complex workflow** - too many commands, manual typing of font names
4. **Poor data tracking** - markdown log file hard to parse and aggregate
5. **No cross-platform merge** - can't easily combine data from macos/wsl/arch systems

## Proposed Solution

### Storage: JSONL (JSON Lines) with Per-Platform Files

Based on research, **JSONL is the optimal choice** for this use case:

**Why JSONL over SQLite:**

- **Text-based**: Easy to merge across computers with git
- **Line-based**: Git-friendly, append-only, easy to concatenate
- **Human-readable**: Can open in text editor for debugging
- **Zero dependencies**: Standard jq tool for querying (already in packages.yml)
- **Unix-friendly**: Works with grep, sort, awk, etc.
- **Mergeable**: Just concatenate files and deduplicate by timestamp

**Avoiding Git Merge Conflicts:**
Use **per-platform history files** to eliminate merge conflicts:

- `history-macos.jsonl` - only written by macos
- `history-arch.jsonl` - only written by arch
- `history-wsl.jsonl` - only written by wsl

Each platform only writes to its own file, so merge conflicts are **impossible**. When reading data, automatically combine all `history-*.jsonl` files in the directory.

**Sources:**

- [JSONL Format Specification](https://jsonlines.org/)
- [Guide to Linux jq Command](https://www.baeldung.com/linux/jq-command-json)
- [What is JSONL?](https://jsonltools.com/what-is-jsonl)

### Data Model

Per-platform JSONL files in `~/.local/share/font/`:

- `history-macos.jsonl`
- `history-arch.jsonl`
- `history-wsl.jsonl`

Read operations automatically combine all `history-*.jsonl` files.

Each line is a JSON record with this structure:

```json
{"ts":"2025-01-15T10:30:00-08:00","platform":"macos","font":"FiraCode Nerd Font","action":"apply"}
{"ts":"2025-01-15T10:35:00-08:00","platform":"macos","font":"FiraCode Nerd Font","action":"like","message":"Great for coding"}
{"ts":"2025-01-15T10:40:00-08:00","platform":"macos","font":"FiraCode Nerd Font","action":"note","message":"Ligatures look good"}
{"ts":"2025-01-15T11:00:00-08:00","platform":"macos","font":"JetBrains Mono Nerd Font","action":"apply"}
{"ts":"2025-01-15T11:05:00-08:00","platform":"macos","font":"JetBrains Mono Nerd Font","action":"dislike","message":"Too narrow"}
```

**Fields:**

- `ts`: ISO 8601 timestamp with timezone
- `platform`: macos, arch, wsl (from $PLATFORM or detected)
- `font`: Full font family name
- `action`: apply, like, dislike, note
- `message`: Optional message (for like/dislike/note actions)

**Platform Detection:**
Use existing logic from install.sh or $PLATFORM environment variable.

### Command Structure (Simplified)

**Commands to KEEP:**

| Command | Description | Example |
|---------|-------------|---------|
| `font current` | Show currently active font | `font current` |
| `font change` | Interactive picker with previews (replaces preview) | `font change` |
| `font apply <font>` | Apply font (internal use, auto-logs) | `font apply "Fira Code"` |
| `font like [message]` | Like current font with optional reason | `font like "Great ligatures"` |
| `font dislike [message]` | Dislike current font with optional reason | `font dislike "Too wide"` |
| `font note <message>` | Add note to current font (REQUIRED message) | `font note "Good for prose"` |
| `font random` | Apply random font from ALL fonts | `font random` |
| `font rank` | Show fonts ranked by likes/dislikes | `font rank` |
| `font log` | View full history log | `font log` |
| `font list` | List all available fonts | `font list` |

**Commands to REMOVE:**

- `font test` - not needed, apply auto-logs
- `font preview` - replaced by `font change`
- `font adventure` - replaced by `font random` (now picks from all)
- `font favorites` - replaced by `font rank` (auto-generated from data)
- Remove hardcoded `FAVORITES` array

**Behavioral Changes:**

1. `font note` - ONLY works on current font, message REQUIRED, no picker
2. `font like/dislike` - Optional message after command
3. `font apply` - Automatically logs apply action with timestamp
4. `font random` - Now picks from ALL fonts (old adventure mode)
5. `font change` - New name for interactive picker (old preview)

### New Commands Detail

#### `font rank`

Show fonts ranked by aggregated likes/dislikes:

```bash
$ font rank

Font Rankings (by activity and sentiment)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. FiraCode Nerd Font
   Score: +5 (6 likes, 1 dislike)
   Last used: 2 days ago (macos)
   Platforms: macos, arch

2. JetBrains Mono Nerd Font
   Score: +3 (4 likes, 1 dislike)
   Last used: 1 week ago (wsl)
   Platforms: macos, wsl

3. SeriousShanns Nerd Font Propo
   Score: +2 (3 likes, 1 dislike)
   Last used: 1 month ago (macos)
   Platforms: macos
```

**Ranking Algorithm:**

- Score = (likes - dislikes)
- Sort by: score DESC, last_used DESC
- Show: rank, font name, score, last usage, platforms tested on

#### `font log`

View complete history, filtered and formatted:

```bash
$ font log

# Default: show last 50 entries
$ font log --all        # Show all entries
$ font log --font "Fira"  # Filter by font name
$ font log --action like  # Filter by action type
$ font log --platform macos  # Filter by platform
```

Output with bat for syntax highlighting if available, otherwise cat.

### Implementation Architecture

#### File Structure

```text
apps/common/font/
├── bin/
│   └── font              # Main CLI (simplified)
├── lib/
│   ├── lib.sh            # Font listing, preview generation (keep existing)
│   └── storage.sh        # NEW: JSONL operations
└── README.md
```

#### storage.sh Functions

```bash
# Core operations
log_action()      # Append action to history.jsonl
get_history()     # Read all history (with optional filters)
get_font_stats()  # Aggregate likes/dislikes per font
get_rankings()    # Calculate and sort font rankings

# Query helpers
filter_by_font()
filter_by_action()
filter_by_platform()
filter_by_date()

# Platform detection
detect_platform() # Returns: macos, arch, wsl
```

#### Example Implementation Snippets

**Log an action:**

```bash
log_action() {
  local action="$1"
  local font="${2:-$(get_current_font)}"
  local message="${3:-}"
  local platform="${PLATFORM:-$(detect_platform)}"
  local timestamp=$(date -Iseconds)  # ISO 8601 with timezone

  # Per-platform history file
  local history_file="$FONT_DATA_DIR/history-${platform}.jsonl"
  mkdir -p "$FONT_DATA_DIR"

  local record
  if [[ -n "$message" ]]; then
    record=$(jq -n \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg font "$font" \
      --arg act "$action" \
      --arg msg "$message" \
      '{ts:$ts, platform:$plat, font:$font, action:$act, message:$msg}')
  else
    record=$(jq -n \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg font "$font" \
      --arg act "$action" \
      '{ts:$ts, platform:$plat, font:$font, action:$act}')
  fi

  echo "$record" >> "$history_file"
}
```

**Get font rankings:**

```bash
get_rankings() {
  # Combine all platform history files and aggregate
  cat "$FONT_DATA_DIR"/history-*.jsonl 2>/dev/null | jq -s '
    group_by(.font) |
    map({
      font: .[0].font,
      likes: map(select(.action == "like")) | length,
      dislikes: map(select(.action == "dislike")) | length,
      score: (map(select(.action == "like")) | length) - (map(select(.action == "dislike")) | length),
      last_used: map(select(.action == "apply")) | max_by(.ts) | .ts // "never",
      platforms: [.[].platform] | unique
    }) |
    sort_by(-.score, -.last_used)
  '
}
```

### Cross-Platform Merging

**Scenario:** You use font tool on macos, arch, and wsl machines.

**Zero-Conflict Merge Strategy:**

Each platform writes only to its own file:

- macos → `history-macos.jsonl`
- arch → `history-arch.jsonl`
- wsl → `history-wsl.jsonl`

**Workflow:**

```bash
# On each machine - commit and push
cd ~/dotfiles
git add ~/.local/share/font/history-*.jsonl
git commit -m "Update font history"
git push

# On another machine - pull
git pull  # NO CONFLICTS! Each platform has its own file
```

**Reading data:**
All read operations automatically combine all `history-*.jsonl` files:

```bash
# This happens automatically in storage.sh
cat ~/.local/share/font/history-*.jsonl 2>/dev/null | jq -s 'sort_by(.ts)'
```

**Benefits:**

- **Zero merge conflicts** - each platform only writes to its own file
- **Automatic sync** - just commit/push/pull normally
- **Cross-platform view** - see combined history from all machines
- **Platform filtering** - can easily filter by platform in queries

## Implementation Steps

### Phase 1: Storage Layer (storage.sh)

- [ ] Create `apps/common/font/lib/storage.sh`
- [ ] Implement `log_action()` function
- [ ] Implement `get_history()` function
- [ ] Implement `get_font_stats()` function
- [ ] Implement `get_rankings()` function
- [ ] Implement `detect_platform()` function
- [ ] Add filter helpers (by_font, by_action, by_platform)
- [ ] Test with sample data

### Phase 2: Update Main CLI (bin/font)

- [ ] Source storage.sh library
- [ ] Remove FAVORITES array
- [ ] Update `apply_font()` to call `log_action "apply"`
- [ ] Rename `preview_fonts()` to `change_font()` and update command
- [ ] Simplify `add_note()` - remove picker, require message, current font only
- [ ] Update `mark_liked()` to use `log_action "like"`
- [ ] Update `mark_disliked()` to use `log_action "dislike"`
- [ ] Update `random_favorite()` to pick from ALL fonts (rename to `random_font()`)
- [ ] Implement new `show_rankings()` function
- [ ] Update `show_log()` to use JSONL data
- [ ] Remove `start_test()`, `adventure_mode()`
- [ ] Update usage() text

### Phase 3: Command Dispatcher Updates

- [ ] Replace `preview` with `change`
- [ ] Remove `test`, `adventure`, `favorites` commands
- [ ] Add `rank` command → `show_rankings()`
- [ ] Update `random` command → `random_font()` (from all fonts)
- [ ] Update `note` command handler (no args allowed)
- [ ] Update `like`/`dislike` handlers (optional message)
- [ ] Update `log` command → new JSONL-based log viewer

### Phase 4: Migration & Testing

- [ ] Create migration script to convert old font-testing-log.md to history.jsonl
- [ ] Test all commands with sample data
- [ ] Verify jq is in packages.yml (it is - checked)
- [ ] Test cross-platform detection
- [ ] Document new workflow in docs/

### Phase 5: Documentation

- [ ] Update `docs/reference/workflow-tools/font.md`
- [ ] Update `docs/workflows/font-testing.md`
- [ ] Add `docs/learnings/font-jsonl-storage.md` explaining the design choice
- [ ] Add section on cross-platform merging

## Migration Strategy

**Convert existing font-testing-log.md → history.jsonl:**

Create a one-time migration script:

```bash
#!/usr/bin/env bash
# migrate-font-log.sh

OLD_LOG="$HOME/.local/share/font/font-testing-log.md"
NEW_LOG="$HOME/.local/share/font/history.jsonl"

if [[ ! -f "$OLD_LOG" ]]; then
  echo "No old log to migrate"
  exit 0
fi

if [[ -f "$NEW_LOG" ]]; then
  echo "New log already exists, skipping migration"
  exit 0
fi

# Parse markdown and convert to JSONL
# This is best-effort - manual review recommended
# For now, just create empty history file and let user rebuild naturally
touch "$NEW_LOG"
echo "Migration: Created new history.jsonl"
echo "Old log backed up to: ${OLD_LOG}.backup"
cp "$OLD_LOG" "${OLD_LOG}.backup"
```

**Recommendation:** Don't try to parse the markdown. Just start fresh with new tracking. The old log can remain as backup.

## Testing Checklist

- [ ] `font current` - shows current font
- [ ] `font change` - interactive picker works
- [ ] `font apply "Fira Code"` - applies and logs action
- [ ] `font like` - logs like for current font (no message)
- [ ] `font like "great"` - logs like with message
- [ ] `font dislike "too wide"` - logs dislike with message
- [ ] `font note "testing"` - logs note for current font
- [ ] `font note` with no message - shows error
- [ ] `font random` - picks from all fonts
- [ ] `font rank` - shows rankings
- [ ] `font log` - displays history
- [ ] Platform detection works on macos/wsl/arch
- [ ] JSONL file is valid JSON per line
- [ ] Merging multiple history files works

## Benefits of New System

1. **Simpler**: 10 commands → 10 commands, but more logical grouping
2. **Automatic**: No manual file editing, no hardcoded favorites
3. **Data-driven**: Rankings emerge from usage patterns
4. **Cross-platform**: Easy to merge history across machines
5. **Flexible**: jq queries enable custom analysis
6. **Git-friendly**: Line-based format works well with version control
7. **Future-proof**: Can add new actions without schema changes
8. **Debuggable**: Human-readable text format

## Open Questions

1. **Track history.jsonl in dotfiles repo?**
   - Pro: Automatic backup and sync
   - Con: Contains personal usage data
   - **Decision:** Track it, it's just font preferences

2. **Default behavior for font random?**
   - Currently picks from hardcoded favorites
   - New: picks from ALL fonts
   - **Decision:** Yes, makes it more adventurous

3. **Require message for note?**
   - **Decision:** Yes, makes intent explicit

4. **Old log file handling?**
   - **Decision:** Keep as backup, don't try to parse

## Timeline Estimate

- **Phase 1 (Storage):** 2-3 hours
- **Phase 2 (CLI Updates):** 2-3 hours
- **Phase 3 (Commands):** 1-2 hours
- **Phase 4 (Testing):** 1-2 hours
- **Phase 5 (Docs):** 1 hour

**Total:** 7-11 hours of focused work

## Success Criteria

- [ ] All new commands work as specified
- [ ] Old commands removed cleanly
- [ ] JSONL format validated
- [ ] Works on macos (testable now)
- [ ] Documentation updated
- [ ] No manual file editing required
- [ ] Cross-platform merge demonstrated
- [ ] Rankings show meaningful data after 1 week of use

---

## References

**JSONL Format:**

- [JSON Lines Official Spec](https://jsonlines.org/)
- [JSONL Format Guide](https://jsonltools.com/what-is-jsonl)
- [JSONL vs JSON](https://www.atatus.com/glossary/jsonl/)

**jq Tool:**

- [jq Official Site](https://jqlang.org/)
- [jq Tutorial](https://jqlang.org/tutorial/)
- [Guide to Linux jq Command](https://www.baeldung.com/linux/jq-command-json)
- [How to Use jq](https://www.linode.com/docs/guides/using-jq-to-process-json-on-the-command-line/)

**Storage Options Research:**

- [Ask HN: Lightweight data analytics with SQLite/Bash](https://news.ycombinator.com/item?id=38793571)
- [Simpler than SQLite - Stack Overflow](https://stackoverflow.com/questions/2012900/simpler-than-sqlite)
