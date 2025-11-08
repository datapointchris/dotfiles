# Menu Fixes - Round 3 (2025-11-07)

## Issues Fixed

### 1. Navigation: Ctrl-h/l for Back/Forward ✅

**User Request:** "Is it possible to have ctrl h and ctrl l be select and back? That would be convenient since ctrl j and ctrl k are up and down, that keeps everything very vim like but with only holding ctrl which is perfect and then allows to search when releasing ctrl."

**Solution:**

- Added `--bind='ctrl-l:accept'` for selecting items (forward)
- Added `--expect='ctrl-h'` to capture back navigation
- Ctrl-j/k for up/down (default fzf)
- All navigation uses Ctrl modifier - release Ctrl to type in search

**Files Modified:**

- `common/.local/bin/menu-new` - Updated FZF_OPTS and menu functions

**Navigation Keys:**

```
Ctrl-j/k - Move up/down
Ctrl-h   - Go back one level
Ctrl-l   - Select item (forward)
Esc      - Exit completely
```

### 2. Esc Behavior: Exit Completely ✅

**User Request:** "In that case, escape could exit completely, which is also convenient to quickly exit the menu."

**Solution:**

- Removed MENU_LEVEL tracking (no longer needed)
- Esc always exits the menu immediately
- Ctrl-h goes back one level
- Simpler mental model: Esc = exit, Ctrl-h = back

**Files Modified:**

- `common/.local/bin/menu-new` - Removed MENU_LEVEL logic
- Updated main_menu() and category_menu() to handle Ctrl-h separately

**Behavior:**

```
Main Menu (Ctrl-h → exit, Esc → exit)
  └─ Category Menu (Ctrl-h → back to Main, Esc → exit)
```

### 3. Session Preview: Syntax Highlighting ✅

**User Request:** "It would be nice to have syntax highlighting in the terminal preview if possible."

**Solution:**

- Added bat integration for syntax highlighting
- Pipes tmux capture-pane output through bat with bash language detection
- Falls back to plain output if bat unavailable
- Uses `--style=plain --paging=never` for clean output in preview

**Files Modified:**

- `common/.local/bin/session-preview-content` - Added bat integration

**Example:**

```bash
# With bat (syntax highlighted):
tmux capture-pane ... | bat --color=always --style=plain --language=bash

# Without bat (plain):
tmux capture-pane ... (shows plain text)
```

### 4. Session Switching: Debug Logging & Background Execution ⏳

**User Feedback:** "Also, selecting a session does not do anything, it just goes back to the pane I was in previously."

**Current Status:**

- Added extensive debug logging
- Modified execution: switch-client runs in background with delay
- Theory: Popup needs to close before switch-client takes effect

**Changes Made:**

```bash
# Run switch-client in background after small delay
(sleep 0.1 && tmux switch-client -t "$session_cmd") &
sleep 0.2  # Wait for it to queue
exit 0     # Close popup
```

**Debug Info Added:**

- Logs item_id and session_cmd
- Logs TMUX_PANE and is_in_tmux status
- Logs which code path is taken (tmux vs session vs sess)

**Next Steps:**

- Test session switching from popup
- Check debug output in stderr
- May need alternative approach if background execution doesn't work

**Files Modified:**

- `common/.local/bin/menu-new` - Added debug logging and background execution

## Testing Checklist

- [ ] Navigation with Ctrl-j/k works smoothly
- [ ] Ctrl-h goes back from category to main menu
- [ ] Ctrl-l selects items
- [ ] Esc exits immediately from any level
- [ ] Can type in search field without Ctrl (including hjkl)
- [ ] Session preview shows syntax highlighting (if bat installed)
- [ ] Session switching works from popup (check debug logs)

## Files Changed

**Modified:**

- `common/.local/bin/menu-new` - Navigation, Esc behavior, session switching debug
- `common/.local/bin/session-preview-content` - Added bat syntax highlighting
- `tools/menu-go/scripts/menu` - Source copy updated

## Navigation Summary

**Old (Round 2):**

- Ctrl-n/p or Ctrl-j/k for up/down
- Enter to select
- Esc to go back (main level) or exit (category level)

**New (Round 3):**

- Ctrl-j/k for up/down
- Ctrl-h to go back
- Ctrl-l to select
- Esc to exit completely
- All navigation on Ctrl modifier
- Release Ctrl to type in search field

## Known Issues

1. **Session switching** - Still debugging
   - Added background execution with delay
   - Added debug logging to diagnose
   - May need alternative approach (temp file, different tmux command)

## User Instructions

### To Test

1. Open menu: `menu-new`
2. Navigate with `Ctrl-j/k`
3. Select with `Ctrl-l`
4. Go back with `Ctrl-h`
5. Exit with `Esc`
6. Try session switching - look for debug output
7. Check if session preview has syntax highlighting

### Navigation Quick Reference

```
Ctrl-j    - Down
Ctrl-k    - Up
Ctrl-h    - Back
Ctrl-l    - Select
Ctrl-d/u  - Page down/up
Ctrl-/    - Toggle preview
/         - Search (type without Ctrl)
Esc       - Exit completely
```

## Next Steps

1. Test session switching with new background execution approach
2. Review debug logs to diagnose any remaining issues
3. Consider alternative approaches if needed:
   - Write session name to temp file, switch after popup closes
   - Use different tmux command or target
   - Copy sesh's exact approach
4. Remove debug logs once everything works
5. Polish and finalize
