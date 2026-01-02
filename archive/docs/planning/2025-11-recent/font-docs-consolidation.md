# Font Documentation Consolidation Plan

## Problem

Font documentation is scattered across multiple locations and too verbose:

1. `docs/workflows/font-testing.md` - Workflow guide (user already trimmed this significantly in git)
2. `docs/getting-started/fonts.md` - Quick start guide
3. `docs/reference/workflow-tools/font.md` - Tool reference
4. User also created `apps/common/font/data/README.md` - Should be in docs instead

**Font reference docs** (these stay, they're about fonts in general):

- `docs/reference/fonts/nerd-fonts-explained.md`
- `docs/reference/fonts/font-weights-and-variants.md`
- `docs/reference/fonts/font-comparison.md`
- `docs/reference/fonts/font-pruning-rules.md`
- `docs/reference/fonts/terminal-fonts-guide.md`

## User's Style Preference

Looking at git diff on `docs/workflows/font-testing.md`:

**BEFORE (verbose - what to avoid):**

- Long "The Problem" and "Philosophy" sections
- Over-explained concepts
- Multiple paragraphs of motivation
- "Success Metrics" sections

**AFTER (concise - what user wants):**

- Direct workflow steps
- Commands shown, not over-explained
- Bullet points for key info
- No fluff or philosophy
- Short and actionable

## Solution

**Consolidate to ONE document:** `docs/apps/font.md`

This becomes THE reference for the font tool with:

- Brief overview (2-3 sentences)
- Quick start (essential commands)
- Command reference (from current help, expanded)
- Data/history section (from data/README.md)
- Links to font reference docs
- SHORT and CONCISE throughout

## Updated Help/Usage

Current `--help` is basic. Enhance it with:

**Formatting inspiration from theme-sync:**

- `print_header` with color for title
- `print_section` with colors for different sections
- Colored command examples
- Unicode bullets
- Clear visual hierarchy

**Structure:**

```bash
print_header "Font Testing & Management" "cyan"
echo "Data-driven font tracking with automatic rankings"
echo ""

print_section "Commands" "blue"
  current              Show currently active font
  change               Interactive font picker with previews
  apply <font>         Apply font to Ghostty/Neovim (auto-logs)
  like [message]       Like current font with optional reason
  dislike [message]    Dislike current font with optional reason
  note <message>       Add note to current font (message required)
  random               Apply random font from all available fonts
  rank                 Show fonts ranked by likes/dislikes
  log                  View complete history
  list                 List all available font families

print_section "Examples" "yellow"
  print_cyan "font change"                    # Interactive picker
  print_cyan "font like \"Great ligatures\""  # Like with reason
  print_cyan "font note \"Good for prose\""   # Add note
  print_cyan "font rank"                      # See rankings

print_section "Data Storage" "green"
  history files location
  git tracking info
  recovery behavior
```

## Implementation Steps

### 1. Delete Old Files

- [ ] Delete `~/.local/share/font/font-testing-log.md`
- [ ] Check symlinks manager for references to old font locations
- [ ] Delete `apps/common/font/data/README.md` (content moved to docs)

### 2. Create Enhanced Help

- [ ] Add formatting.sh sourcing to font script
- [ ] Rewrite usage() function with colors and sections
- [ ] Model after theme-sync help output
- [ ] Test help output looks good

### 3. Consolidate Documentation

- [ ] Read all three existing docs (workflows, getting-started, reference)
- [ ] Extract essential content from each
- [ ] Create `docs/apps/font.md` with:
  - Overview (2-3 sentences)
  - Quick Start (5-10 commands max)
  - Commands (reference style, short)
  - Data & History (from data/README.md)
  - Cross-Platform Usage (JSONL per-platform)
  - Links to related font docs
- [ ] Keep it SHORT - follow user's trimmed style from git diff
- [ ] Delete old docs after consolidation

### 4. Update mkdocs.yml

- [ ] Add `Apps` section if it doesn't exist
- [ ] Add `docs/apps/font.md` to navigation
- [ ] Remove old font doc entries:
  - `docs/workflows/font-testing.md`
  - `docs/getting-started/fonts.md`
  - `docs/reference/workflow-tools/font.md`
- [ ] Keep font reference docs (they're general font knowledge)

### 5. Git Commits Strategy

Make targeted commits that pass pre-commit:

**Commit 1:** "feat(font): add enhanced help with colors and formatting"

- Update font script with new usage() function
- Minimal doc update: add placeholder docs/apps/font.md with basics

**Commit 2:** "refactor(font): consolidate documentation to docs/apps/font.md"

- Create complete docs/apps/font.md
- Delete old docs
- Update mkdocs.yml

**Commit 3:** "chore(font): remove deprecated files and update symlinks"

- Delete old font-testing-log.md
- Remove data/README.md
- Update symlinks if needed

## Content Outline for docs/apps/font.md

```markdown
# Font Tool

Automatic font tracking with data-driven rankings.

## Quick Start

\`\`\`bash
font change          # Interactive picker
font like "reason"   # Like current font
font rank            # See rankings
\`\`\`

## Commands

### Viewing

- `font current` - Show active font
- `font list` - List available fonts
- `font rank` - Font rankings by likes/dislikes
- `font log` - View complete history

### Applying Fonts

- `font change` - Interactive picker with previews
- `font apply <font>` - Apply by name (auto-logs)
- `font random` - Random from all fonts

### Tracking

- `font like [message]` - Like current font
- `font dislike [message]` - Dislike current font
- `font note <message>` - Add note to current font

### Utilities

- `font generate-previews` - Pre-generate preview images
- `font clear-cache` - Clear preview cache

## Data & History

Font history is stored in per-platform JSONL files:

\`\`\`
apps/common/font/data/
├── history-macos.jsonl
├── history-arch.jsonl
└── history-wsl.jsonl
\`\`\`

**Benefits:**
- Git-tracked automatically
- Zero merge conflicts (each platform has its own file)
- Cross-platform rankings (combines all platforms)
- Auto-recreates if deleted

View history with `font log` to see file locations for manual editing.

## How It Works

Each action (apply, like, dislike, note) appends a timestamped JSON record:

\`\`\`json
{"ts":"2025-11-26T11:06:21-05:00","platform":"macos","font":"Fira Code","action":"like","message":"Great ligatures"}
\`\`\`

Rankings aggregate likes/dislikes across all platforms to surface your favorites.

## See Also

- [Nerd Fonts Explained](../reference/fonts/nerd-fonts-explained.md)
- [Font Weights and Variants](../reference/fonts/font-weights-and-variants.md)
- [Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md)
\`\`\`

## Style Guidelines

- Keep it SHORT and DIRECT
- No philosophy or motivation sections
- Commands and examples, not explanations
- Bullet points over paragraphs
- Imperative tone ("View history" not "You can view history")
- No "success metrics" or fluff
- Link to reference docs instead of explaining fonts
