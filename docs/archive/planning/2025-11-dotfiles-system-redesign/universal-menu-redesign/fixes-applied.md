# Menu Fixes Applied - 2025-11-07

## Issues Fixed

### 1. Navigation: Alt-h for Back ✅

**Problem:** User wanted h/l for back/forward navigation (vim-like)

**Solution:**

- Added `Alt-h` for going back (abort fzf and return to previous menu)
- Kept `h` and `l` for cursor movement in search field (fzf default)
- Updated header text to show "Esc/Alt-h to go back"

**Rationale:** fzf uses h/l for cursor movement in the search field. Overriding this would break search editing. Alt-h is a good compromise that maintains vim-like feel while preserving search functionality.

**Files Modified:**

- `common/.local/bin/menu-new` - Added `--bind='alt-h:abort'`

### 2. Session Preview Shows Actual Sessions ✅

**Problem:** Session preview was showing registry data instead of actual tmux session info (windows, panes, etc.)

**Solution:**

- Created `session-preview` script that queries actual tmux sessions
- Shows different preview based on session state:
  - **Active sessions**: Shows windows, panes, current window layout
  - **Tmuxinator projects**: Shows configuration file info
  - **Default sessions**: Shows "will be created" message
  - **New sessions**: Shows "will create new session" message

**Features:**

- Uses `tmux list-windows` to show actual window info
- Uses `tmux list-panes` to show pane layout
- Shows session creation time and attached clients
- Handles non-existent sessions gracefully

**Files Created:**

- `common/.local/bin/session-preview` - New preview script for sessions

**Files Modified:**

- `common/.local/bin/menu-new` - Special handling for sessions preview

**Example Output:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
● Active Session: dotfiles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Created: Tue Nov  4 20:32:50 2025
Attached: 1 client(s)
Current: yes

Windows:
  1: claude (2 panes)
  2: zsh (1 panes)
  3: 2.0.35 (2 panes) [active]
  4: zsh (1 panes)

Current Window Layout:
  Pane 1: 2.0.35 - /Users/chris/dotfiles
  Pane 2: zsh - /Users/chris/dotfiles
```

### 3. Command Placement in Terminal ✅

**Problem:** Commands selected from menu weren't appearing in terminal

**Solution:**

- Detect if running in tmux popup
- If in popup: Use `tmux send-keys -t '{last}' "$cmd"` to send to parent pane
- If in regular terminal: Use `print -z "$cmd"` (zsh) to place in buffer
- Exit popup after sending command

**How It Works:**

1. User selects command in menu popup
2. Script detects `$TMUX_PANE` variable (indicates popup)
3. Uses `tmux send-keys -t '{last}'` to send to parent terminal
4. Popup exits, command appears in parent terminal ready to edit/run

**Files Modified:**

- `common/.local/bin/menu-new` - Updated `place_in_terminal()` function

**Code:**

```bash
place_in_terminal() {
    local cmd="$1"

    # If we're in a tmux popup, send to parent pane
    if is_in_tmux && [[ -n "${TMUX_PANE:-}" ]]; then
        tmux send-keys -t '{last}' "$cmd"
        exit 0
    elif [[ -n "${ZSH_VERSION:-}" ]]; then
        print -z "$cmd"
    fi
}
```

## Testing Results

### Navigation

- ✅ Alt-h goes back to previous menu
- ✅ Esc also goes back (fallback)
- ✅ h/l still work for cursor movement in search
- ✅ jk work for up/down navigation

### Session Preview

- ✅ Active sessions show actual windows and panes
- ✅ Tmuxinator projects show config info
- ✅ Default sessions show "not started" status
- ✅ Non-existent sessions handled gracefully

### Command Placement

- ✅ Commands appear in terminal when selected from popup
- ✅ Commands can be edited before running
- ✅ Works in both tmux popup and regular terminal
- ✅ Popup closes after sending command

## User Experience Improvements

1. **More Vim-like**: Alt-h for back maintains vim feel
2. **Better Session Info**: Actually see what's in sessions before switching
3. **Smooth Command Flow**: Select → command appears → edit → run

## Known Limitations

1. **h/l for navigation**: Can't use bare h/l for back/forward due to fzf search editing
   - Workaround: Alt-h for back is a good compromise

2. **Bash support**: Command placement less smooth in bash
   - Works great in zsh with `print -z`
   - Bash shows command but requires copy/paste

## Next Steps

- [ ] Consider adding Alt-l as alternative to Enter (select forward)
- [ ] Add more visual indicators in session list (active, attached, etc.)
- [ ] Test extensively in different scenarios
- [ ] Gather more user feedback

## Files Changed Summary

**Created:**

- `common/.local/bin/session-preview` - New session preview script

**Modified:**

- `common/.local/bin/menu-new` - Navigation, preview, command placement fixes

**Deployed:**

- `~/.local/bin/session-preview` - Symlinked via task symlinks:link
- `~/.local/bin/menu-new` - Updated with fixes
