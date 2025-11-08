# Universal Menu System - Phase 1 Implementation Complete

**Created:** 2025-11-06
**Previous:** 03-context_and_workflow_decisions.md
**Status:** Phase 1 Complete - Ready for Testing

---

## Phase 1 Completed Tasks

### 1. Symlinks Taskfile Created ✓

Created `taskfiles/symlinks.yml` with comprehensive tasks for the symlinks Python tool:

**Available tasks:**
- `task symlinks:link` - Create symlinks (common + platform)
- `task symlinks:show` - Show current symlinks
- `task symlinks:check` - Check for broken symlinks
- `task symlinks:relink` - Complete refresh
- And more...

**Note:** The symlinks tool is installed via `uv` as a Python package, not a simple script. It lives at `~/.local/share/uv/tools/dotfiles-symlinks/bin/symlinks` and is properly symlinked to `~/.local/bin/symlinks`.

### 2. Universal Menu Script Created ✓

Created `common/.local/bin/menu` with:

**Features:**
- Context-aware menu using gum for display
- Detects git project name
- Shows project-specific categories (Tasks, Todo) only when applicable
- Universal categories always available
- Tmux-aware (shows Sessions when in tmux)

**Categories Implemented:**
- **Tools** → Uses existing `tools` command
- **Aliases** → Parses `~/.shell/aliases.sh` with fzf
- **Functions** → Parses `~/.shell/fzf-functions.sh` with fzf
- **Project: {name}** → Shows tasks (if Taskfile.yml exists)
- **Todo** → Shows todo.md (if exists in project)
- **Tmux** → Shows sessions (if in tmux)

**Context Detection:**
```bash
get_project_name()  # Gets basename of git root
is_in_git_repo()    # Checks if in git repository
has_taskfile()      # Checks for Taskfile.yml in git root
has_todo()          # Checks for todo.md in git root
is_in_tmux()        # Checks $TMUX environment variable
```

### 3. Aerospace Hotkey Added ✓

Added to `macos/.config/aerospace/aerospace.toml` (line 66):
```toml
alt-shift-m = 'exec-and-forget ghostty -e menu'
```

**Usage:** Press **Alt+Shift+M** from anywhere in macOS to launch a new Ghostty window with the menu.

### 4. Tmux Keybinding Added ✓

Added to `common/.config/tmux/tmux.conf` (line 95):
```tmux
bind m run-shell -b 'menu'
```

**Usage:** Press **Prefix+m** (Ctrl-Space then m) when in tmux to run menu in current pane.

### 5. Symlinks Relinked ✓

Ran `task symlinks:relink` to deploy the new menu script.

**Result:**
- Removed 31 platform symlinks
- Removed 101 common symlinks
- Created 103 common symlinks (including new `menu` script)
- Created 31 platform symlinks
- ✓ Menu is now at `~/.local/bin/menu`

---

## How to Test

### From Outside Terminal (macOS System-Level)

1. **Reload Aerospace config:**
   ```bash
   aerospace reload-config
   ```

2. **Press Alt+Shift+M** from anywhere (browser, editor, desktop)
   - Should launch new Ghostty window with menu
   - Should show categories with gum

3. **Select a category** with arrow keys and Enter
   - **Tools** → Shows your tools list
   - **Aliases** → Shows aliases with fzf
   - **Functions** → Shows functions with fzf
   - **Project: dotfiles** → Shows Task commands (you're in dotfiles project)

### From Inside Terminal (Tmux)

1. **Reload tmux config:**
   ```bash
   tmux source-file ~/.config/tmux/tmux.conf
   ```

2. **In a tmux pane, press Ctrl-Space then m**
   - Should run menu inline in current pane
   - Should show same categories as above
   - Plus **Tmux** → Sessions (since you're in tmux)

### Testing in Different Projects

1. **Navigate to a different git project:**
   ```bash
   cd ~/other-project
   ```

2. **Run menu** (either Alt+Shift+M or Prefix+m)
   - Should show "Project: other-project" if it has a Taskfile
   - Should show "Todo" if it has a todo.md
   - Should NOT show dotfiles-specific stuff

3. **Navigate outside git:**
   ```bash
   cd ~
   ```

4. **Run menu**
   - Should only show universal categories (Tools, Aliases, Functions)
   - No project-specific categories

---

## Current Menu Structure

```
Universal Categories (Always):
  ├── Tools → CLI tools discovery
  ├── Aliases → Shell aliases (parsed from aliases.sh)
  └── Functions → Shell functions (parsed from fzf-functions.sh)

Context-Aware Categories:
  ├── Project: {name} → Tasks (if Taskfile.yml exists)
  ├── Todo → {project}/todo.md (if exists)
  └── Tmux → Sessions (if $TMUX is set)
```

---

## Known Limitations / Future Work

### Not Yet Implemented

1. **Bookmarks** (buku integration) - Deferred
2. **Learning resources** - Deferred
3. **Git category** - Should be easy to add
4. **Scripts category** - Should scan .local/bin
5. **Execution of selected items** - Currently just shows, doesn't execute

### Potential Improvements

1. **Execute actions from menu**
   - Currently aliases/functions show but don't execute
   - Could bind Enter to execute selected item
   - Would need to handle different contexts (copy to clipboard, execute, open URL, etc.)

2. **Tmux popup**
   - Use `tmux display-popup` instead of inline
   - More space, cleaner interface
   - Example: `bind m display-popup -E -w 80% -h 80% 'menu'`

3. **Preview windows**
   - Add better previews for all categories
   - Show full alias definition
   - Show function body
   - Show task description

4. **Git functions**
   - Add category for git helpers (fco_preview, fshow_preview, fstash, etc.)
   - Parse fzf-functions.sh for git-specific functions

5. **Scripts discovery**
   - Scan .local/bin dynamically
   - Filter out dotfiles-specific scripts when not in dotfiles
   - Show description from script header comments

---

## File Locations

**Menu Script:**
- Source: `dotfiles/common/.local/bin/menu`
- Symlink: `~/.local/bin/menu`

**Configuration:**
- Aerospace: `dotfiles/macos/.config/aerospace/aerospace.toml` (line 66)
- Tmux: `dotfiles/common/.config/tmux/tmux.conf` (line 95)

**Dependencies:**
- `gum` (installed via `brew install gum`)
- `fzf` (already installed)
- `yq` (already installed, for task parsing)

**Context Files:**
- Aliases: `~/.shell/aliases.sh` or `~/dotfiles/common/.shell/aliases.sh`
- Functions: `~/.shell/fzf-functions.sh` or `~/dotfiles/common/.shell/fzf-functions.sh`
- Tasks: `{git_root}/Taskfile.yml`
- Todo: `{git_root}/todo.md`

---

## Next Steps

### Immediate Testing (Do Now)

1. Reload configs:
   ```bash
   aerospace reload-config
   tmux source-file ~/.config/tmux/tmux.conf
   ```

2. Test both hotkeys:
   - Alt+Shift+M (from anywhere)
   - Ctrl-Space then m (in tmux)

3. Navigate between projects and verify context awareness

4. Report any issues or desired improvements

### Phase 2 (When Phase 1 Tested)

Based on your feedback, we can:

1. **Add execution to menu items**
   - Make aliases/functions actually run
   - Make tasks execute with confirmation

2. **Add Git category**
   - List git helper functions
   - Show their usage examples

3. **Refine UX**
   - Better previews
   - Tmux popup option
   - Help text / hints

4. **Add Scripts category**
   - Scan .local/bin
   - Show descriptions
   - Context-aware filtering

### Later Phases (Deferred)

- Buku bookmarks integration
- Learning resources organization
- Todo list management
- Additional context awareness

---

## Success Criteria

Phase 1 is successful if:

- ✓ Menu launches from both hotkeys (Alt+Shift+M and Prefix+m)
- ✓ Shows universal categories everywhere
- ✓ Shows project categories only when in git repo with Taskfile
- ✓ Shows tmux category only when in tmux
- ✓ Different projects show different project names
- ✓ All categories display their content correctly

---

## Summary

**What Works:**
- Context-aware universal menu
- Two hotkey launch methods (system and tmux)
- Dynamic category list based on context
- Universal categories: Tools, Aliases, Functions
- Project categories: Tasks, Todo (when applicable)
- Tmux category (when in tmux)

**Ready to Test:**
All Phase 1 implementation is complete and ready for user testing. The menu script is deployed, hotkeys are configured, and the system is context-aware as planned.

**Next Document:**
Will be created after user testing and feedback, documenting Phase 2 plans and any refinements based on real-world usage.
