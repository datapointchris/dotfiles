# Phase 2: Polish & Category Validation

**Created:** 2025-11-07
**Status:** Ready to implement
**Estimated Time:** 2-3 hours with thorough testing

## Overview

Phase 1 is complete and working! Now we need to:

1. Validate all categories work properly
2. Add polish to previews where beneficial
3. Test edge cases thoroughly
4. Document final behavior

## Proposed Work Items

### 1. Category Validation (Priority: HIGH)

**Goal:** Ensure all 5 categories work correctly end-to-end

#### Commands (c)

- [x] List commands - WORKING
- [x] Preview shows description/examples - WORKING
- [x] Selecting places command in terminal - WORKING
- [ ] Test with commands that have no examples
- [ ] Test with commands with special characters ($, `, etc.)
- [ ] Test with multi-line command definitions

**Testing Script:**

```bash
# Open menu → Commands
# Select: glo (simple)
# Verify: "glo" appears in terminal
# Select: a command with examples
# Verify: Preview shows examples
# Select: a forgit command (special chars)
# Verify: Command places correctly
```

#### Sessions (s)

- [x] List sessions - WORKING
- [x] Preview shows window info with syntax highlighting - WORKING
- [x] Selecting switches to session - WORKING
- [ ] Test with no active sessions
- [ ] Test with tmuxinator projects
- [ ] Test with session names containing spaces

**Testing Script:**

```bash
# Open menu → Sessions
# Test: Select active session → should switch
# Test: Select tmuxinator project → should launch
# Test: Verify preview shows windows/panes correctly
```

#### Workflows (w)

- [x] List workflows - WORKING
- [x] Preview shows steps - WORKING
- [ ] Test behavior when selecting workflow
- [ ] Define what "selecting" does (show full workflow? copy steps?)
- [ ] Test with workflows with many steps

**Testing Script:**

```bash
# Open menu → Workflows
# Select: "Quickfix List - Search and Replace"
# Verify: Shows "Selected: ..." message
# Question: Should we do more? Copy to clipboard? Open in editor?
```

#### Learning (l)

- [x] List learning topics - WORKING
- [x] Preview shows resources - WORKING
- [ ] Test behavior when selecting topic
- [ ] Define what "selecting" does (open in browser? editor?)
- [ ] Test with topics with many resources

**Testing Script:**

```bash
# Open menu → Learning
# Select a topic
# Verify: Shows confirmation or performs action
# Question: Should we open links? Show details?
```

#### Tools (t)

- [x] List tools - WORKING
- [x] Preview shows tool info - WORKING
- [ ] Test behavior when selecting tool
- [ ] Define what "selecting" does (launch tool? show docs?)
- [ ] Test with different tool types

**Testing Script:**

```bash
# Open menu → Tools
# Select a tool
# Verify: Expected behavior happens
# Question: What should happen?
```

### 2. Preview Enhancements (Priority: MEDIUM)

#### Command Previews with Syntax Highlighting

Currently command previews show examples as plain text. We could add bat syntax highlighting like we did for sessions.

**Before:**

```
Examples:
  fcd ~/projects
  fcd
```

**After (with bat):**

```
Examples:
  fcd ~/projects  # (syntax highlighted as bash)
  fcd
```

**Implementation:**

- Modify `preview.go` to wrap example commands in bat
- Test with commands that have multiple examples
- Ensure fallback if bat not available

**Testing:**

```bash
# Open menu → Commands → fcd
# Verify: Examples have syntax highlighting
# Test with bat removed: Verify plain text fallback
```

### 3. Edge Case Testing (Priority: HIGH)

#### Empty Registries

- [ ] Test with no commands in commands registry
- [ ] Test with no workflows
- [ ] Test with no learning topics
- [ ] Verify graceful handling (shows message, doesn't crash)

#### Special Characters

- [ ] Command with $ in name
- [ ] Command with backticks
- [ ] Session name with spaces
- [ ] Workflow title with quotes

#### Large Lists

- [ ] Test with 100+ commands (performance)
- [ ] Test fzf filtering with large list
- [ ] Test preview generation speed

#### Shell Context

- [ ] Test in zsh (primary shell)
- [ ] Test in bash if available
- [ ] Test outside tmux
- [ ] Test in nested tmux

### 4. Behavior Documentation (Priority: MEDIUM)

Document what happens when you select each category type:

**Commands:** Places alias/command name in terminal buffer
**Sessions:** Switches to session (creates if doesn't exist)
**Workflows:** Shows selection (future: could do more?)
**Learning:** Shows selection (future: could do more?)
**Tools:** Shows selection (future: could launch tool?)

## Testing Strategy

For each work item, I will:

1. **Write test script** - Bash script to test functionality
2. **Run tests** - Execute and capture output
3. **Document results** - Pass/fail with actual output
4. **Fix issues** - If tests fail, fix and re-test
5. **Report to user** - Show test results, not just "should work"

## Example Test Script Format

```bash
#!/usr/bin/env bash
# Test: Commands category end-to-end

echo "=== Test 1: List commands ==="
result=$(menu-go-new list commands | wc -l)
echo "Commands found: $result"
if [[ $result -gt 0 ]]; then
    echo "✓ PASS"
else
    echo "✗ FAIL: No commands found"
    exit 1
fi

echo ""
echo "=== Test 2: Get simple command ==="
result=$(menu-go-new get commands glo)
expected="glo"
if [[ "$result" == "$expected" ]]; then
    echo "✓ PASS: $result"
else
    echo "✗ FAIL: Expected '$expected', got '$result'"
    exit 1
fi

# ... more tests
```

## Deliverables

1. **Test suite** - Scripts in `dev/active/universal-menu-redesign/tests/`
2. **Test results** - Documented pass/fail for each category
3. **Bug fixes** - Any issues found and fixed
4. **Behavior documentation** - Clear description of what each category does
5. **Updated progress.md** - Phase 2 completion status

## Questions for User

Before starting, I need to decide:

1. **Workflows selection** - What should happen? Options:
   - Just show "Selected: ..." (current)
   - Copy all steps to clipboard
   - Open workflow in editor
   - Show in pager (less/bat)

2. **Learning selection** - What should happen? Options:
   - Just show "Selected: ..." (current)
   - Open first link in browser
   - Copy resources to clipboard
   - Show in pager

3. **Tools selection** - What should happen? Options:
   - Just show "Selected: ..." (current)
   - Launch the tool (if executable)
   - Show tool documentation
   - Copy tool command to clipboard

4. **Syntax highlighting** - Should command examples have bat highlighting?
   - Pro: Looks nicer, consistent with session preview
   - Con: Adds dependency, slight performance hit
   - Fallback: Plain text if bat unavailable

## Proposed Next Step

Start with **Category Validation** (highest priority), specifically:

1. Test Commands category thoroughly (already mostly working)
2. Test Sessions category thoroughly (mostly working, needs edge cases)
3. Test Workflows, Learning, Tools categories
4. Document what each does when selected
5. Fix any issues found

Then move to edge case testing and enhancements.

Does this approach sound good?
