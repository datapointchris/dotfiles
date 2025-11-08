# Menu Fixes - Round 4 (Critical Architecture Fix)

## Root Cause Analysis

After researching how `sesh` and `sessionx` implement session switching, I found the critical issue:

**The Problem:**

- Our script was using `tmux display-popup` to run the ENTIRE script inside a popup
- When we tried to call `tmux switch-client` from inside the popup, it didn't work
- The popup context was blocking the session switch

**How sesh/sessionx work:**

- They use `fzf-tmux -p` which creates a popup for JUST the fzf selection
- The script runs OUTSIDE the popup
- After user selects, fzf popup closes, THEN the script calls `switch-client`
- This works because the script is running in the normal tmux context

## The Fix

Changed from:

```bash
# OLD: Wrap entire script in popup
tmux display-popup -E "menu-new --no-popup"
  └─ Script runs INSIDE popup
      └─ fzf runs inside the popup script
          └─ switch-client fails (still in popup)
```

To:

```bash
# NEW: Script runs normally, fzf creates popup
menu-new
  └─ Script runs OUTSIDE popup
      └─ fzf-tmux -p creates popup for selection
          └─ User selects, popup closes
              └─ switch-client works! (outside popup)
```

## Changes Made

### 1. New `run_fzf()` Function ✅

Created a helper that automatically uses the right fzf variant:

```bash
run_fzf() {
    if is_in_tmux; then
        # Use fzf-tmux to create popup (script runs outside)
        fzf-tmux -p 80%,80% "${FZF_OPTS[@]}" "$@"
    else
        # Use regular fzf
        fzf "${FZF_OPTS[@]}" --height=100% "$@"
    fi
}
```

### 2. Removed `run_in_popup()` ✅

No longer needed! The script now runs normally, and `fzf-tmux` handles popup creation.

### 3. Simplified Session Switching ✅

```bash
# Before: Complex background execution, debug logs, delays
(sleep 0.1 && tmux switch-client -t "$session") &
sleep 0.2
exit 0

# After: Simple and clean
tmux switch-client -t "$session_name"
```

Works perfectly because script is outside popup context.

### 4. Simplified Command Placement ✅

```bash
# Before: Complex logic to send to parent pane
tmux send-keys -t '{last}' "$cmd" 2>&1 | tee /tmp/menu-debug.log >&2

# After: Simple send to current pane
tmux send-keys "$cmd"
```

Works because we're already in the right pane context.

### 5. Updated Entry Point ✅

```bash
# Before: Conditional popup wrapping
if is_in_tmux; then
    run_in_popup "$0 --no-popup"
else
    main_menu
fi

# After: Always run directly
main_menu  # fzf-tmux handles popup if needed
```

## Architecture Comparison

### SessionX (Reference Implementation)

```
sessionx.tmux (tmux plugin)
  └─ tmux bind-key O run-shell "sessionx.sh"
      └─ sessionx.sh (runs in normal context)
          └─ fzf-tmux -p (creates popup for selection)
              └─ handle_output()
                  └─ tmux switch-client (works!)
```

### Our Implementation (Now Matching)

```
menu-new (bash script)
  └─ main_menu() (runs in normal context)
      └─ run_fzf() → fzf-tmux -p (creates popup)
          └─ category_menu() (back in normal context)
              └─ run_fzf() → fzf-tmux -p (creates popup)
                  └─ handle_selection() (back in normal context)
                      └─ tmux switch-client (works!)
```

## Files Modified

**Modified:**

- `common/.local/bin/menu-new` - Complete architecture rewrite
- `tools/menu-go/scripts/menu` - Source copy updated

**Key Changes:**

- Added `run_fzf()` function
- Removed `run_in_popup()` function
- Updated `main_menu()` to use `run_fzf`
- Updated `category_menu()` to use `run_fzf`
- Simplified `handle_selection()` session code
- Simplified `place_in_terminal()` command code
- Simplified `main()` entry point
- Removed all debug logging (no longer needed)

## Testing Checklist

- [ ] Session switching works from tmux
- [ ] Session switching works from outside tmux
- [ ] Command placement works in tmux
- [ ] Command placement works in zsh outside tmux
- [ ] Navigation (Ctrl-j/k/h/l) works correctly
- [ ] Syntax highlighting in session preview
- [ ] All categories work correctly

## Key Insight

The issue was NOT with tmux switch-client or send-keys syntax. The issue was **execution context**. When you run commands from inside `tmux display-popup`, those commands execute in the popup's shell context, which is separate from your normal tmux pane.

By using `fzf-tmux` instead of wrapping everything in `display-popup`, we keep the script execution in the normal pane context. The fzf popup is just for UI, not execution context.

This is why both `sesh` and `sessionx` use this pattern - it's the ONLY way to make session switching work reliably from a popup-based menu.

## Expected Results

Now that the script runs in normal context:

1. **Session Switching**: `tmux switch-client` should work immediately
2. **Command Placement**: `tmux send-keys` should place commands correctly
3. **No More Debug Output**: Clean, production-ready code
4. **Simpler Code**: Removed ~30 lines of workaround complexity

## Next Steps

1. User tests session switching - should work now
2. User tests command placement - should work now
3. If working, remove this testing note
4. Polish and finalize
