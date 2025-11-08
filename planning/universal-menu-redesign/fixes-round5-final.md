# Menu Fixes - Round 5 (Final Critical Fixes)

## Root Cause Analysis

After the user reported two critical issues, I properly investigated and tested to find the root causes:

### Issue 1: Session Switching Error

**User Report:** "can't find window: /Users/chris/"

**Root Cause:** The `get` command in `get.go` was returning `selectedItem.Command` instead of `selectedItem.ID`.

For sessions:

- ID = "dotfiles" (the session name we want)
- Command = "/Users/chris/.local/bin/session dotfiles" (the full command to run)

When we passed this to `tmux switch-client`, it tried to find a window named "/Users/chris/.local/bin/session" which doesn't exist.

### Issue 2: Commands Outputting Full Expansion

**User Report:** "for glo it is not outputting glo but instead git log --oneline --graph --decorate"

**Root Cause:** Same issue - `get` command was returning `selectedItem.Command` instead of `selectedItem.ID`.

For commands:

- ID = "glo" (the alias we want to place in terminal)
- Command = "git log --oneline --graph --decorate" (the full expansion)

Users want the alias name (glo) in their terminal, not the full expansion.

### Issue 3: Workflows Causing Errors

**User Report:** "for any of the vim workflows, if I select it then it tries to input that text on the command line"

**Root Cause:** The `extract_id()` function was only extracting the first word before the arrow:

```bash
# OLD (WRONG):
echo "$line" | awk '{print $1}'
# "Quickfix List - Search and Replace → desc" → "Quickfix" (wrong!)

# NEW (CORRECT):
echo "$line" | awk -F ' → ' '{print $1}'
# "Quickfix List - Search and Replace → desc" → "Quickfix List - Search and Replace" (correct!)
```

This caused `menu-go get` to fail finding the workflow, and likely caused errors.

## Fixes Applied

### Fix 1: get.go - Return ID Not Command ✅

**File:** `tools/menu-go/internal/cli/get.go` (line 63-73)

**Old Code:**

```go
if selectedItem.Command != "" {
    fmt.Println(selectedItem.Command)  // WRONG - returns full expansion
} else {
    fmt.Println(selectedItem.ID)
}
```

**New Code:**

```go
// For commands/sessions, return the ID (the name to place in terminal)
// NOT the Command field which contains the full expansion
//
// Examples:
//   - Command "glo": ID="glo", Command="git log --oneline" → return "glo"
//   - Session "dotfiles": ID="dotfiles", Command="session dotfiles" → return "dotfiles"
//
// The ID is what the user wants to place in their terminal or pass to tmux
fmt.Println(selectedItem.ID)
```

**Impact:**

- Commands now return alias name: "glo" instead of "git log --oneline..."
- Sessions now return session name: "dotfiles" instead of "/Users/chris/.local/bin/session dotfiles"

### Fix 2: extract_id() - Extract Full Text Before Arrow ✅

**File:** `common/.local/bin/menu-new` (line 57-65)

**Old Code:**

```bash
extract_id() {
    local line="$1"
    line="${line#★ }"
    echo "$line" | awk '{print $1}'  # WRONG - only first word
}
```

**New Code:**

```bash
extract_id() {
    local line="$1"
    line="${line#★ }"
    # Extract everything before → (the arrow)
    echo "$line" | awk -F ' → ' '{print $1}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}
```

**Impact:**

- Single-word IDs: "glo" → "glo" ✓
- Multi-word IDs: "Quickfix List - Search and Replace" → "Quickfix List - Search and Replace" ✓
- With favorites: "★ glo" → "glo" ✓

### Fix 3: Rebuilt Binary ✅

Rebuilt `menu-go-new` binary with the fixed `get.go`:

```bash
go build -o ~/.local/bin/menu-go-new ./cmd/menu-cli
```

## Testing Results

### Automated Tests ✅

```bash
# Test 1: Command with single word ID
menu-go-new get commands glo
# Expected: glo
# Got: glo ✓

# Test 2: Session name
menu-go-new get sessions dotfiles
# Expected: dotfiles
# Got: dotfiles ✓

# Test 3: Workflow with multi-word title
menu-go-new get workflows "Quickfix List - Search and Replace"
# Expected: Quickfix List - Search and Replace
# Got: Quickfix List - Search and Replace ✓

# Test 4: Extract single word
extract_id "glo → Pretty git log"
# Expected: glo
# Got: glo ✓

# Test 5: Extract multi-word
extract_id "Quickfix List - Search and Replace → Description"
# Expected: Quickfix List - Search and Replace
# Got: Quickfix List - Search and Replace ✓

# Test 6: Extract with favorite star
extract_id "★ glo → Pretty git log"
# Expected: glo
# Got: glo ✓
```

## Files Modified

**Go Source:**

- `tools/menu-go/internal/cli/get.go` - Changed to return ID instead of Command

**Bash Scripts:**

- `common/.local/bin/menu-new` - Fixed extract_id() function
- `tools/menu-go/scripts/menu` - Source copy updated

**Binaries:**

- `~/.local/bin/menu-go-new` - Rebuilt with fixed get.go

## Expected Behavior

### Commands

1. User opens menu → Commands
2. User selects "glo"
3. Menu calls: `menu-go get commands glo`
4. Returns: "glo"
5. Calls: `tmux send-keys "glo"`
6. Result: "glo" appears in terminal ✓

### Sessions

1. User opens menu → Sessions
2. User selects "dotfiles"
3. Menu calls: `menu-go get sessions dotfiles`
4. Returns: "dotfiles"
5. Calls: `tmux switch-client -t "dotfiles"`
6. Result: Switches to dotfiles session ✓

### Workflows (Informational)

1. User opens menu → Workflows
2. User selects "Quickfix List - Search and Replace"
3. Menu calls: `menu-go get workflows "Quickfix List - Search and Replace"`
4. Returns: "Quickfix List - Search and Replace"
5. Calls: `echo "Selected: ..."`
6. Result: Shows confirmation message (doesn't try to execute) ✓

## Why These Fixes Work

The core misunderstanding was about what the `Command` field represents:

**For Commands (aliases/functions):**

- ID = The short name the user types (glo)
- Command = The full expansion (git log --oneline)
- What user wants = ID (to place in terminal)

**For Sessions:**

- ID = The session name (dotfiles)
- Command = The command to create/attach (session dotfiles)
- What user wants = ID (to pass to tmux switch-client)

**For Workflows:**

- ID = The workflow title (Quickfix List - Search and Replace)
- Command = Empty (informational only)
- What user wants = ID (for display/reference)

The `get` command should ALWAYS return the ID, not the Command. The Command field is for internal use by the integration to know how to execute the item if needed.

## User-Facing Changes

**Before:**

- Selecting "glo" → tried to execute "git log --oneline --graph --decorate" in terminal
- Selecting "dotfiles" session → error "can't find window: /Users/chris/"
- Selecting workflow → error or partial match

**After:**

- Selecting "glo" → places "glo" in terminal ✓
- Selecting "dotfiles" session → switches to dotfiles session ✓
- Selecting workflow → shows selection confirmation ✓

## Validation

All issues from user's report should now be fixed:

- ✅ Session switching works (no more "can't find window" error)
- ✅ Commands place alias name, not expansion
- ✅ Workflows don't try to execute

Ready for final user testing.
