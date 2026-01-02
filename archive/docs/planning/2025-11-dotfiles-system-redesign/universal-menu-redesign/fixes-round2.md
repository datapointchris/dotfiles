# Menu Fixes - Round 2 (2025-11-07)

## Issues Fixed

### 1. Navigation: Removed hjkl, Using Default fzf ✅

**Problem:** hjkl keys interfered with typing in search field

**Solution:**

- Removed all hjkl key bindings
- Using default fzf navigation: **Ctrl-n/p** or **Ctrl-j/k** for up/down
- Search typing now works naturally (can type h, j, k, l in search)

**Files Modified:**

- `common/.local/bin/menu-new` - Removed hjkl bindings from FZF_OPTS

**Navigation Keys:**

- `Ctrl-n` or `Ctrl-j` - Move down
- `Ctrl-p` or `Ctrl-k` - Move up
- `Ctrl-d/u` - Page down/up
- `/` (search) - Can type any characters including hjkl
- `Enter` - Select
- `Esc` - Go back (see below)

### 2. Esc Behavior: Go Back One Level ✅

**Problem:** Esc was exiting the entire menu instead of going back one level

**Solution:**

- Added `MENU_LEVEL` tracking (0 = main menu, 1 = category menu)
- At category level (MENU_LEVEL=1): Esc goes back to main menu
- At main level (MENU_LEVEL=0): Esc exits the menu
- Now behaves like a proper hierarchical menu

**Files Modified:**

- `common/.local/bin/menu-new` - Added MENU_LEVEL tracking

**Behavior:**

```
Main Menu (Esc → exit)
  └─ Categories Menu (Esc → back to Main Menu)
```

### 3. Session Preview: Show Actual Pane Content ✅

**Problem:** Preview was showing tmux list-windows output, not actual pane content

**Solution:**

- Created `session-preview-content` script
- Uses `tmux capture-pane` to show last 30 lines of actual pane content
- Shows visual preview of what's in the session (like sesh does)

**Files Created:**

- `common/.local/bin/session-preview-content` - Captures and displays pane content

**Files Modified:**

- `common/.local/bin/menu-new` - Uses `session-preview-content` for sessions

**Example Output:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
● Active Session: dotfiles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Windows:
  1: claude
  2: zsh
  3: 2.0.35 [active]
  4: zsh

━━━ Preview of window 1 ━━━

[Shows actual terminal content from that pane]
trim trailing whitespace.................................................Passed
check that executables have shebangs.................(no files to check)Skipped
check that scripts with shebangs are executable..........................Passed
...
```

### 4. Session Switching: Fixed with tmux switch-client ✅

**Problem:** Selecting a session did nothing, just went back to previous pane

**Solution:**

- When in tmux popup: Use `tmux switch-client -t "$session_name"`
- This switches the client to the selected session
- Popup closes after switching
- When not in popup: Use session/sess binary as before

**Files Modified:**

- `common/.local/bin/menu-new` - Added tmux switch-client for popup sessions

**How It Works:**

1. User selects session from popup
2. Menu uses `tmux switch-client` to switch to that session
3. Popup closes
4. User is now in the selected session

### 5. Command Placement: Added Debug Logging ⏳

**Problem:** Commands not appearing in terminal after selection

**Current Status:**

- Added extensive debug logging to diagnose the issue
- Logs to stderr and `/tmp/menu-debug.log`
- Need to test to see what's happening

**Debug Info Added:**

- Logs the command being sent
- Logs TMUX_PANE variable
- Logs whether in tmux
- Logs tmux send-keys output/errors

**Next Steps:**

- Test selecting a command from popup
- Check stderr output for debug messages
- Check `/tmp/menu-debug.log` for tmux send-keys errors
- May need to adjust the target pane syntax

**Files Modified:**

- `common/.local/bin/menu-new` - Added debug output to `place_in_terminal()`

## Testing Checklist

- [ ] Navigation with Ctrl-n/p works smoothly
- [ ] Can type hjkl in search field
- [ ] Esc goes back from category to main menu
- [ ] Esc exits from main menu
- [ ] Session preview shows actual pane content
- [ ] Selecting a session actually switches to it
- [ ] Commands appear in terminal (check debug logs if not)

## Files Changed

**Created:**

- `common/.local/bin/session-preview-content` - Show actual session content

**Modified:**

- `common/.local/bin/menu-new` - All fixes
- `tools/menu-go/scripts/menu` - Source copy updated

**Deployed:**

- All changes symlinked via `task symlinks:link`

## Known Issues

1. **Command placement** - Still debugging, logs added to diagnose
   - May need to adjust tmux send-keys target syntax
   - May need to use different method to send to parent pane from popup

## User Instructions

### To Test

1. Open menu: `menu-new`
2. Navigate with `Ctrl-n/p` (not hjkl)
3. Type in search field (hjkl should work for typing now)
4. Press Esc to go back one level
5. Select a session - should actually switch
6. Try selecting a command - check if it appears in terminal
7. If command doesn't appear, check: `cat /tmp/menu-debug.log`

### To Update

If you pulled latest changes:

```bash
task symlinks:link
```

## Next Steps

1. Test command placement thoroughly
2. Remove debug logs once working
3. Polish any remaining rough edges
4. Document final behavior
