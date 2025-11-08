# Universal Menu Redesign - Tasks

**Created:** 2025-11-07
**Last Updated:** 2025-11-07
**Status:** Planning Complete, Ready to Implement

## Current Status

- [x] Fix sess script BSD compatibility bug
- [x] Analyze existing implementations
- [x] Create comprehensive planning document
- [ ] Begin implementation

## Phase 1: Core fzf Integration (Week 1)

### 1.1 Create CLI Commands

- [ ] Create `internal/cli/` package structure
- [ ] Implement `root.go` with Cobra setup
- [ ] Implement `list-categories` command
  - [ ] Returns: `s → Sessions`, `c → Commands`, etc.
  - [ ] Test with different terminals
- [ ] Implement `list <integration>` command
  - [ ] `list sessions` → session entries with format
  - [ ] `list commands` → command entries with format
  - [ ] `list workflows` → workflow entries
  - [ ] `list learning` → learning topics
  - [ ] Test with empty registries
  - [ ] Test with large registries (100+ items)
- [ ] Implement `preview <type> <id>` command
  - [ ] Preview sessions with window/pane info
  - [ ] Preview commands with description, examples, notes
  - [ ] Preview workflows with steps
  - [ ] Preview learning topics with resources
  - [ ] Test preview generation speed (<100ms)
- [ ] Implement `get <type> <id>` command
  - [ ] Returns raw command string for execution
  - [ ] Test with special characters
  - [ ] Test with multi-line commands

### 1.2 Format Output for fzf

- [ ] Create `internal/formatter/` package
- [ ] Implement `fzf.go` with list formatting
  - [ ] `FormatForFzf(items []Item) string`
  - [ ] Format: `id → description` or similar
  - [ ] Test with unicode characters
  - [ ] Test with long descriptions (truncation?)
- [ ] Implement `preview.go` with preview formatting
  - [ ] `FormatPreview(item Item) string`
  - [ ] Use ANSI color codes (not hardcoded)
  - [ ] Format title with separator
  - [ ] Format examples with syntax
  - [ ] Format steps as numbered list
  - [ ] Test with different item types
  - [ ] Test preview width handling
- [ ] Test with different terminal color schemes
  - [ ] light theme
  - [ ] dark theme
  - [ ] theme-sync generated themes
- [ ] Verify no hardcoded colors

### 1.3 Create Bash Wrapper

- [ ] Create `tools/menu-go/scripts/menu`
- [ ] Implement tmux detection
  - [ ] Check `$TMUX` variable
  - [ ] Use `tmux display-popup` if in tmux
  - [ ] Fallback to fullscreen if not in tmux
  - [ ] Test nested tmux sessions
- [ ] Configure fzf with keybindings
  - [ ] `ctrl-j:down, ctrl-k:up` (always work)
  - [ ] `j:down, k:up` (if not filtering)
  - [ ] `ctrl-h:backward-char, ctrl-l:forward-char`
  - [ ] `ctrl-d:half-page-down, ctrl-u:half-page-up`
  - [ ] `ctrl-/:toggle-preview`
  - [ ] Test all bindings work
- [ ] Wire up preview command
  - [ ] Call `menu-go preview <type> <id>`
  - [ ] Ensure preview updates on navigation
  - [ ] Test preview with long content
- [ ] Implement main menu flow
  - [ ] List categories with fzf
  - [ ] Show category preview
  - [ ] On select, call category menu
- [ ] Implement category menu flow
  - [ ] List items in category
  - [ ] Show item preview
  - [ ] On select, handle action
- [ ] Test complete flow
  - [ ] Main → Commands → Select → Command in terminal
  - [ ] Main → Sessions → Select → Switch session
  - [ ] Test Esc to go back
  - [ ] Test Ctrl-C to quit

### 1.4 Shell Integration

- [ ] Implement command placement for zsh
  - [ ] Use `print -z "command"`
  - [ ] Test command appears in buffer
  - [ ] Test can edit before executing
  - [ ] Test with special characters
- [ ] Handle tmux popup → parent pane
  - [ ] Detect if in tmux popup
  - [ ] Use `tmux send-keys -t {last}` to parent
  - [ ] Test command appears in parent pane
  - [ ] Decide: auto-execute or place only?
- [ ] Test in both environments
  - [ ] Test in tmux popup
  - [ ] Test in regular terminal
  - [ ] Test without tmux
  - [ ] Verify command placement works

**Phase 1 Success Criteria:**

- [ ] Can open menu (popup if in tmux)
- [ ] Can select "Commands" category
- [ ] Can navigate with hjkl
- [ ] Preview updates as you move
- [ ] Enter places command in terminal
- [ ] No execution happens in menu
- [ ] All tests pass

## Phase 2: Polish & Navigation (Week 1-2)

### 2.1 Enhanced Navigation

- [ ] Verify `/` filtering works in fzf
  - [ ] Test filter and preview update together
  - [ ] Test clearing filter
- [ ] Add `Ctrl-/` to toggle preview
  - [ ] Test on/off toggle
  - [ ] Test preview remembers state
- [ ] Add `Ctrl-d/u` for page navigation
  - [ ] Test half-page down
  - [ ] Test half-page up
- [ ] Test vim muscle memory
  - [ ] hjkl should feel natural
  - [ ] No lag or unexpected behavior
  - [ ] Test rapid navigation

### 2.2 Preview Enhancements

- [ ] Enhance command previews
  - [ ] Syntax highlight code examples (if using bat)
  - [ ] Format related commands list
  - [ ] Show platform indicator
  - [ ] Test with commands that have no examples
- [ ] Enhance workflow previews
  - [ ] Format steps as numbered list
  - [ ] Show keybindings in box
  - [ ] Highlight current step somehow?
  - [ ] Test with workflows with many steps
- [ ] Enhance learning previews
  - [ ] Group resources by type (bookmark, note, video)
  - [ ] Show progress indicator
  - [ ] Format practice exercises as checklist
  - [ ] Test with topics with many resources
- [ ] Enhance session previews
  - [ ] Show window list
  - [ ] Show active indicator
  - [ ] Show pane count per window
  - [ ] Test with sessions with many windows

### 2.3 Sessions Integration

- [ ] Make sessions actually switch
  - [ ] Call `session` binary or `sess` script
  - [ ] Don't just copy command
  - [ ] Test switching between sessions
- [ ] Show active sessions with indicator
  - [ ] Use `●` or similar for active
  - [ ] Use `○` or similar for inactive
  - [ ] Test indicator appears correctly
- [ ] Preview shows session details
  - [ ] Window names and count
  - [ ] Pane configuration
  - [ ] Current directory
  - [ ] Test with tmuxinator projects

**Phase 2 Success Criteria:**

- [ ] hjkl navigation feels natural (like yazi/vim)
- [ ] Previews are informative and well-formatted
- [ ] Filtering with `/` works smoothly
- [ ] Sessions switch on Enter without extra steps
- [ ] Preview toggle works reliably

## Phase 3: All Categories (Week 2)

### 3.1 Implement Each Category

#### Sessions (s)

- [ ] List active sessions, tmuxinator projects, defaults
- [ ] Preview shows windows/panes
- [ ] Enter switches to session
- [ ] Test with no active sessions
- [ ] Test with many sessions (10+)

#### Commands (c)

- [ ] List all commands from registry
- [ ] Preview shows description, examples, notes
- [ ] Enter places command in terminal
- [ ] Test with empty commands registry
- [ ] Test filtering by keyword

#### Workflows (w)

- [ ] List all workflows from registry
- [ ] Preview shows steps and keybindings
- [ ] Enter... does what? (TBD - maybe just informational)
- [ ] Test with complex multi-step workflows

#### Learning (l)

- [ ] List learning topics from registry
- [ ] Preview shows resources, progress, exercises
- [ ] Enter... opens first resource? (TBD)
- [ ] Test with topics with many resources

#### Tools (t)

- [ ] List tools from registry
- [ ] Preview shows tldr or description
- [ ] Enter shows full docs?
- [ ] Test with tools that have tldr
- [ ] Test with tools without tldr

#### Tasks (if Taskfile present)

- [ ] Detect Taskfile.yml in current repo
- [ ] List tasks from Taskfile
- [ ] Preview shows task description
- [ ] Enter executes task (this one DOES execute)
- [ ] Test in repo with Taskfile
- [ ] Test in repo without Taskfile

### 3.2 Category-Specific Behavior

Document behavior for each:

| Category | Enter Action | Notes |
|----------|--------------|-------|
| Sessions | Switch session | Execute immediately |
| Commands | Place in terminal | User edits/executes |
| Workflows | Show in preview | Informational only |
| Learning | Copy first URL? | TBD |
| Tools | Show tldr | Informational |
| Tasks | Execute task | Show output |

- [ ] Implement action handlers for each category
- [ ] Test each action works correctly
- [ ] Document behavior in help text

**Phase 3 Success Criteria:**

- [ ] All categories work
- [ ] Each category has appropriate action
- [ ] Previews are consistent across categories
- [ ] Help text explains what Enter does

## Phase 4: Quality & Testing (Week 2-3)

### 4.1 Testing

#### Unit Tests

- [ ] Test `list` commands
  - [ ] list-categories
  - [ ] list sessions
  - [ ] list commands
  - [ ] list workflows
  - [ ] list learning
  - [ ] list tools
- [ ] Test `preview` commands
  - [ ] preview for each type
  - [ ] preview with missing items
  - [ ] preview with invalid IDs
- [ ] Test `get` commands
  - [ ] get command
  - [ ] get with special characters
- [ ] Test formatters
  - [ ] FormatForFzf with various items
  - [ ] FormatPreview with all item types
  - [ ] ANSI color code output

#### Integration Tests

- [ ] Test complete flows
  - [ ] main menu → commands → select
  - [ ] main menu → sessions → switch
  - [ ] main menu → workflows → view
- [ ] Test with fixtures
  - [ ] Empty registries
  - [ ] Large registries (100+ items)
  - [ ] Malformed YAML (error handling)

#### Manual Tests

- [ ] Test in different terminal emulators
  - [ ] iTerm2
  - [ ] Ghostty
  - [ ] Terminal.app
  - [ ] Alacritty
- [ ] Test with different color schemes
  - [ ] Light theme
  - [ ] Dark theme
  - [ ] Custom theme-sync themes
- [ ] Test tmux vs non-tmux
  - [ ] Popup in tmux
  - [ ] Fullscreen without tmux
  - [ ] Nested tmux
- [ ] Test on macOS (primary platform)
  - [ ] Sonoma
  - [ ] Different screen sizes

### 4.2 Error Handling

- [ ] Handle missing YAML files
  - [ ] Show friendly error message
  - [ ] Suggest creating file
- [ ] Handle empty categories
  - [ ] Show "No items found"
  - [ ] Suggest adding items
- [ ] Handle invalid item IDs
  - [ ] Show "Item not found"
  - [ ] List valid IDs?
- [ ] Handle tmux errors
  - [ ] Popup fails
  - [ ] Fallback to fullscreen
- [ ] Show helpful error messages
  - [ ] Not just stack traces
  - [ ] Suggest fixes when possible

### 4.3 Performance

- [ ] Ensure previews generate quickly
  - [ ] Measure preview generation time
  - [ ] Target: <100ms per preview
  - [ ] Profile if slow
- [ ] Cache YAML parsing if needed
  - [ ] Measure YAML load time
  - [ ] Cache if > 100ms
  - [ ] Invalidate cache on file change
- [ ] Profile with large registries
  - [ ] Test with 100+ commands
  - [ ] Test with 50+ workflows
  - [ ] Ensure no lag in navigation

**Phase 4 Success Criteria:**

- [ ] All tests pass
- [ ] No visible lag (<100ms preview)
- [ ] Works across terminal emulators
- [ ] Respects terminal color scheme
- [ ] Handles errors gracefully

## Phase 5: Documentation & Polish (Week 3)

### 5.1 Documentation

- [ ] Update menu-go README
  - [ ] New architecture section
  - [ ] Explain hybrid Go + fzf design
  - [ ] Update usage examples
  - [ ] Update installation instructions
- [ ] Document bash wrapper script
  - [ ] How it works
  - [ ] Environment variables
  - [ ] Customization options
- [ ] Document CLI commands
  - [ ] `menu-go list-categories`
  - [ ] `menu-go list <type>`
  - [ ] `menu-go preview <type> <id>`
  - [ ] `menu-go get <type> <id>`
- [ ] Add examples for extending registries
  - [ ] How to add a command
  - [ ] How to add a workflow
  - [ ] How to add learning topic
- [ ] Document tmux keybinding setup
  - [ ] Add to tmux.conf
  - [ ] Customize popup size
  - [ ] Alternative keybindings

### 5.2 Tmux Integration

- [ ] Add tmux.conf snippet

  ```
  bind m display-popup -E -w 80% -h 80% -d "#{pane_current_path}" 'menu'
  ```

- [ ] Test popup sizing
  - [ ] 80% feels right?
  - [ ] Try 70%, 90%
  - [ ] Test on different screen sizes
- [ ] Test popup positioning
  - [ ] Should be centered
  - [ ] Test on ultrawide monitors
  - [ ] Test on laptop screens
- [ ] Ensure popup works in nested tmux
  - [ ] Test nested sessions
  - [ ] Test popup from popup

### 5.3 Final Polish

- [ ] Add help text to fzf headers
  - [ ] "hjkl to navigate"
  - [ ] "/ to filter"
  - [ ] "Enter to select"
  - [ ] "Esc to go back"
- [ ] Consistent formatting across previews
  - [ ] Same header style
  - [ ] Same section separators
  - [ ] Same color usage
- [ ] Remove old Bubble Tea code
  - [ ] Remove internal/ui/
  - [ ] Remove Bubble Tea dependencies
  - [ ] Update go.mod
- [ ] Clean up unused dependencies
  - [ ] Run go mod tidy
  - [ ] Check for unused imports

**Phase 5 Success Criteria:**

- [ ] Documentation is clear and complete
- [ ] Tmux integration works perfectly
- [ ] Code is clean and maintainable
- [ ] No dead code or unused dependencies

## Post-Launch Tasks

### Migration & Cutover

- [ ] Keep old binary as `menu-old`
- [ ] Switch symlink to new binary
- [ ] Monitor for issues
- [ ] Collect user feedback
- [ ] Address any bugs

### Future Enhancements

- [ ] Bash shell support (currently zsh only)
- [ ] Fish shell support
- [ ] Syntax highlighting in previews (bat integration)
- [ ] Favorites indicators in lists (★)
- [ ] Sort by recents
- [ ] Custom keybindings config
- [ ] Export/import registries

### Cleanup

- [ ] Remove Bubble Tea completely after stable
- [ ] Archive old approach documentation
- [ ] Update all related docs
- [ ] Create migration guide

## Notes

- Keep task list updated as work progresses
- Mark completed tasks with date
- Document any blockers or issues
- Link to related commits/PRs

## Blockers & Issues

(None currently)

## Questions & Decisions Needed

1. **Learning category Enter action:** What should happen?
   - Option A: Copy first URL to clipboard
   - Option B: Just show in preview (no action)
   - Option C: Open in browser
   - **Decision:** TBD

2. **Workflows category Enter action:** What should happen?
   - Option A: Copy first step command
   - Option B: Just show in preview (no action)
   - **Decision:** TBD

3. **Preview syntax highlighting:** Use bat or keep simple?
   - Option A: Use bat for code examples (more dependencies)
   - Option B: Keep simple with ANSI (lighter)
   - **Decision:** Start simple, add bat later if needed

4. **Bash compatibility:** How much effort for bash support?
   - Option A: Start with zsh only
   - Option B: Try to support both from start
   - **Decision:** Start zsh, add bash in future

## Timeline

- **Week 1 (Nov 7-13):** Phase 1 & 2 (Core + Polish)
- **Week 2 (Nov 14-20):** Phase 3 & 4 (All Categories + Testing)
- **Week 3 (Nov 21-27):** Phase 5 (Documentation + Polish)
- **Week 4 (Nov 28+):** Migration & Launch

**Last Updated:** 2025-11-07 - Planning complete, ready to implement
