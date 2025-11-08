# Preview Fix - Multi-Word ID Support

**Issue:** Workflows and Learning items with multi-word IDs showed "item not found: [FirstWord]" in preview
**Date:** 2025-11-07
**Status:** ✅ Fixed and tested

## Problem Description

When hovering over workflows or learning topics with multi-word titles in fzf, the preview pane showed errors:

```
Error: item not found: Neovim
Error: item not found: Git
```

**Example:**

- Item: "Neovim Quickfix Lists → Master quickfix lists"
- Preview received: "Neovim" (just first word)
- Should receive: "Neovim Quickfix Lists" (full ID before arrow)

## Root Cause

The fzf preview command was using `{1}` which only passes the first field (word) to the preview command:

```bash
# OLD (BROKEN):
preview_cmd="$MENU_GO_PATH preview $integration {1}"
```

**What was happening:**

1. fzf shows: "Neovim Quickfix Lists → Description"
2. Preview uses `{1}` → "Neovim"
3. menu-go-new tries to find "Neovim" (doesn't exist)
4. Error: "item not found: Neovim"

**What should happen:**

1. fzf shows: "Neovim Quickfix Lists → Description"
2. Preview extracts ID → "Neovim Quickfix Lists"
3. menu-go-new finds "Neovim Quickfix Lists" ✓
4. Shows correct preview ✓

## Solution

Created a helper script that extracts the full ID from the fzf line before calling preview.

### Step 1: Created menu-preview-helper Script

**File:** `common/.local/bin/menu-preview-helper`

```bash
#!/usr/bin/env bash
# Helper script to extract ID from fzf line and call preview
# Usage: menu-preview-helper <integration> <fzf-line>

set -euo pipefail

MENU_GO_PATH="${MENU_BIN:-menu-go-new}"

integration="$1"
shift
line="$*"

# Extract ID: remove favorite star, get everything before →
line="${line#★ }"
item_id=$(echo "$line" | awk -F ' → ' '{print $1}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# Call preview with extracted ID
"$MENU_GO_PATH" preview "$integration" "$item_id"
```

**What it does:**

1. Takes integration type (workflows, learning, etc.) as first arg
2. Takes full fzf line as remaining args
3. Removes favorite star if present
4. Extracts everything before " → " separator
5. Trims whitespace
6. Calls menu-go-new preview with the correct ID

### Step 2: Updated menu Script

**File:** `common/.local/bin/menu-new` (line 112-114)

```bash
# OLD:
preview_cmd="$MENU_GO_PATH preview $integration {1}"

# NEW:
preview_cmd="menu-preview-helper $integration {}"
```

**Key change:** Using `{}` instead of `{1}`

- `{1}` = first field/word only ("Neovim")
- `{}` = entire line ("Neovim Quickfix Lists → Description")

### Step 3: Made Helper Executable

```bash
chmod +x common/.local/bin/menu-preview-helper
```

## Test Results

All tests passing:

```bash
✓ Multi-word learning topics work
✓ Multi-word workflows work
✓ Commands with favorites work
✓ Single word IDs still work (regression test)
✓ Helper script properly integrated
```

### Test Examples

**Test 1: Learning with multi-word ID**

```bash
$ menu-preview-helper learning "Neovim Quickfix Lists → Master quickfix"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Neovim Quickfix Lists
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[... full preview content ...]
✓ PASS
```

**Test 2: Workflow with multi-word ID**

```bash
$ menu-preview-helper workflows "Git Integration in Neovim → Git operations"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Git Integration in Neovim
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[... full preview content ...]
✓ PASS
```

**Test 3: Command with favorite (regression test)**

```bash
$ menu-preview-helper commands "★ glo → Pretty git log"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
glo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[... full preview content ...]
✓ PASS (favorite star correctly removed)
```

## Files Modified

### New Files Created

**`common/.local/bin/menu-preview-helper`**

- Executable helper script
- Extracts ID from fzf line
- Calls menu-go-new preview with correct ID

### Modified Files

**`common/.local/bin/menu-new`** (line 112-114)

- Changed preview_cmd to use helper with `{}`
- Source: `tools/menu-go/scripts/menu` updated

**`tools/menu-go/scripts/menu-preview-helper`**

- Source copy of helper script

## Why This Approach

**Alternative approaches considered:**

1. **Inline bash -c with complex escaping**

   ```bash
   preview_cmd="bash -c 'line=\"{}\"; ...[complex escaping]...'"
   ```

   ❌ Too complex, hard to maintain, escaping nightmare

2. **Modify menu-go to accept full line**

   ```bash
   menu-go-new preview-with-extraction $integration "{}"
   ```

   ❌ Adds complexity to Go code for bash-specific issue

3. **Helper script (chosen)**

   ```bash
   preview_cmd="menu-preview-helper $integration {}"
   ```

   ✅ Clean separation of concerns
   ✅ Easy to test independently
   ✅ Reusable for other scripts
   ✅ Simple to maintain

## Impact

**Before:**

- ❌ Workflows preview: "Error: item not found: Git"
- ❌ Learning preview: "Error: item not found: Neovim"
- ❌ Any multi-word ID fails in preview
- ✓ Single-word IDs work fine

**After:**

- ✓ Workflows preview: Shows full workflow details
- ✓ Learning preview: Shows full learning topic details
- ✓ All multi-word IDs work correctly
- ✓ Single-word IDs still work (backward compatible)
- ✓ Favorites (★) handled correctly

## User Experience

**Before fix:**

```
[User navigates to Workflows]
[Hovers over "Git Integration in Neovim"]
Preview: Error: item not found: Git
```

**After fix:**

```
[User navigates to Workflows]
[Hovers over "Git Integration in Neovim"]
Preview: [Shows full workflow with steps, resources, etc.]
```

## Edge Cases Tested

1. ✅ Multi-word IDs with spaces
2. ✅ Multi-word IDs with hyphens ("Quickfix List - Search")
3. ✅ IDs with favorite stars (★)
4. ✅ Single-word IDs (regression test)
5. ✅ IDs with special characters
6. ✅ All integration types (workflows, learning, commands, tools)

## Deployment

The helper script needs to be in PATH:

```bash
# Already deployed to:
~/.local/bin/menu-preview-helper  (symlinked via task symlinks:link)

# Source files:
common/.local/bin/menu-preview-helper
tools/menu-go/scripts/menu-preview-helper
```

## Conclusion

The preview issue for multi-word IDs is completely fixed. The solution is clean, testable, and maintains backward compatibility with single-word IDs.

**Status:** ✅ Ready for use - all tests passing
