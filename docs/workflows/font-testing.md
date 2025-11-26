# Font Testing and Management

Systematic approach to testing coding fonts, finding favorites, and maintaining a curated collection.

## The Problem

Too many fonts creates decision paralysis. Scrolling through 63 font families every time, wondering "is this the one?" wastes mental energy better spent coding. The solution is systematic testing over time, building a small collection of proven favorites.

## Philosophy: Less Is More

The goal is not finding the "perfect" font. The goal is finding 3-5 fonts that work well in different contexts, then deleting everything else. Stop searching, start using.

This mirrors the theme-sync workflow: maintain a curated list of favorites, switch easily between them, and stop agonizing over infinite options.

## Current State

- **code_fonts**: 63 font files, ~20 font families
- **new_fonts**: 1,595 proportional fonts (unsuitable for terminal use)
- **Currently using**: SeriousShanns Nerd Font Propo

The code_fonts collection is manageable but needs curation. The new_fonts directory is a hoard that can be archived.

## The Font Testing Workflow

### Quick Start

List available fonts and see the current selection:

```bash
font-sync list     # Show all installed code fonts
font-sync current  # Display current font
```

Apply a font interactively with preview:

```bash
font-sync preview  # fzf-based interactive selector
```

Or apply directly by name:

```bash
font-sync apply "FiraCode Nerd Font Mono"
```

### Systematic Testing Process

Testing a font for one hour reveals nothing. Testing it for a week during real work reveals whether it truly works.

Start tracking a font test:

```bash
font-sync test "JetBrains Mono Nerd Font"
```

Use the font for actual development work:

- Write code across multiple languages
- Read diffs and code reviews
- Debug errors and stack traces
- Browse log files
- Work in your actual environment

Watch for these signals:

- Eye strain after an hour suggests the font won't work long-term
- Struggling to distinguish `0O` or `1lI` means poor character differentiation
- Feeling uneasy or annoyed indicates aesthetic mismatch
- Squinting or leaning forward suggests size or weight issues

After sufficient testing (minimum 3 days, ideally a week), record the decision:

```bash
font-sync like      # Keep this font
# or
font-sync dislike   # Mark for removal
```

Add specific observations:

```bash
font-sync notes "FiraCode Nerd Font" "Great ligatures but too narrow for my taste"
```

### Tracking Progress

View the testing log to see patterns and progress:

```bash
font-sync log
```

The log tracks:

- Currently testing font with start date
- Fonts marked as keepers
- Fonts marked for removal
- Testing history with dates
- Notes and observations

This creates accountability and prevents testing the same font multiple times without remembering previous conclusions.

### Building the Favorites List

As keepers emerge, add them to the favorites array in the font-sync script:

```bash
nvim ~/dotfiles/apps/common/font-sync
```

Edit the FAVORITES array:

```bash
FAVORITES=(
  "SeriousShanns Nerd Font Propo"
  "FiraCode Nerd Font Mono"
  "JetBrains Mono Nerd Font"
  # Add more as discovered
)
```

The favorites list enables quick rotation and random selection without decision fatigue.

### Avoiding Decision Paralysis

When choice paralysis hits, let randomness decide:

```bash
font-sync random      # Random from favorites (safe)
font-sync adventure  # Random from ALL fonts (adventure!)
```

This mirrors the theme-sync random feature that made choosing daily themes effortless. Apply a random font, use it immediately, and know within hours whether it works. No agonizing over perfect choices.

The `adventure` command automatically starts tracking the test, creating a frictionless flow from selection to evaluation.

## Testing Schedule Strategies

### Weekly Testing (Recommended)

**Monday morning**: Apply new font with `font-sync preview` or `font-sync adventure`
**Throughout the week**: Use it in all coding activities
**Friday afternoon**: Decide with `font-sync like` or `font-sync dislike`

At one font per week, testing all 63 fonts takes about a year. But discovering top favorites happens within 8-12 weeks. Stop testing when satisfied with the collection.

### Accelerated Testing

**Three-day cycles**: Test Mon-Wed, decide Thursday, start new font Friday

This completes testing faster but requires enough real coding work during those three days to form valid opinions. A font used only for trivial tasks hasn't been truly tested.

### Extended Testing

**Two weeks per font**: For uncertainty or subtle differences

Some fonts seem fine initially but cause eye strain after prolonged use. Extending testing catches these issues. Others reveal hidden benefits after the initial adjustment period passes.

## What to Observe During Testing

### Technical Readability

Character differentiation matters. Can you instantly distinguish:

- `0` (zero) from `O` (capital O)
- `1` (one) from `l` (lowercase L) from `I` (uppercase i)
- `` ` `` (backtick) from `'` (quote)
- `{[()]}` (brackets are clearly different)

Poor differentiation causes bugs. Excellent differentiation prevents them.

### Physical Comfort

Eye strain signals problems. After one hour, do your eyes feel:

- Tired or strained
- Dry or irritated
- Like squinting helps

After two hours, do you experience:

- Headaches
- Difficulty focusing
- Desire to look away from screen

These signals indicate the font weight, size, or design doesn't suit your eyes and screen combination.

### Aesthetic Alignment

Personal response matters. Does the font:

- Feel "right" for your personality
- Make you look forward to opening the terminal
- Disappear into the background, letting you focus on code
- Feel professional enough for work contexts
- Match the aesthetic of other tools in your environment

Fonts have personality. Some people love the casual feel of Comic Sans-style fonts. Others need clean, professional aesthetics. Neither is wrong. Match the font to your preferences, not someone else's recommendations.

### Functional Requirements

Ligature preference varies by person and language. If coding in JavaScript or Rust with many operators, ligatures might clarify code. If working in Python or Go with fewer operators, ligatures might add noise.

Test with ligatures enabled (remove `-liga` from Ghostty config), then disabled, then decide which feels better.

Width matters for workflow. Narrow fonts like Iosevka fit more code horizontally, beneficial for small screens or split panes. Wider fonts provide more breathing room, beneficial for large screens and long sessions.

## Random Testing Approach

For rapid discovery without overthinking:

```bash
# Let fate decide the next font
font-sync adventure
```

This applies a random font immediately and starts tracking the test. No preview, no second-guessing, no comparison paralysis. Use it for the next few days and see how it feels.

This approach worked for discovering favorite themes. It works equally well for fonts. Thrust into an environment without choice, adaptation happens quickly, revealing genuine preferences.

## Managing the Font Hoard

The 1,595 fonts in new_fonts serve no purpose for terminal or coding work. They are proportional fonts designed for graphic design, not monospace work.

Archive the entire collection:

```bash
font-hoard stats      # Face the reality
font-hoard purge-all  # Create compressed archive
```

This creates `font-archive-YYYYMMDD.tar.gz` containing all fonts, then clears the new_fonts directory. Move the archive to external storage or cloud backup. Delete it after backing up.

If the urge to keep "just in case" appears, examine that impulse honestly. In 40 years, when was the last time a specific decorative font was needed? If the answer is "never" or "I don't remember," the fonts are clutter, not assets.

For the rare case of actually needing a specific font, download it when needed rather than hoarding thousands perpetually.

## After Finding Favorites

Once 3-5 favorite fonts emerge, complete the curation:

Check the testing log:

```bash
font-sync log
```

Identify fonts marked "disliked." Delete them from code_fonts:

```bash
cd ~/Documents/code_fonts
# Manually remove disliked font files
```

Copy favorites to dotfiles for easy reinstallation:

```bash
mkdir -p ~/dotfiles/fonts/favorites
cp ~/Documents/code_fonts/FiraCode*.otf ~/dotfiles/fonts/favorites/
cp ~/Documents/code_fonts/SeriousShanns*.otf ~/dotfiles/fonts/favorites/
# Copy other favorites
```

For automated installation on new systems, create an install script:

```bash
cat > ~/dotfiles/fonts/install.sh <<'EOF'
#!/usr/bin/env bash
cp ~/dotfiles/fonts/favorites/* ~/Library/Fonts/
fc-cache -f
echo "✓ Installed favorite fonts"
EOF

chmod +x ~/dotfiles/fonts/install.sh
```

Alternatively, document which fonts to download from nerdfonts.com rather than storing large font files in git.

## Integration with Theme Sync

Font choice and theme choice create the visual environment. Synchronize them for cohesive aesthetics:

```bash
ghostty-theme apply rose-pine       # Set terminal theme
font-sync apply "FiraCode Nerd Font"  # Set font
theme-sync apply base16-rose-pine   # Set tool themes
```

Or maintain deliberate contrast - light terminal theme with dark tmux panes creates visual boundaries between contexts.

Test font and theme combinations together. A font that looks excellent with one theme might look poor with another due to contrast, color harmony, and overall visual weight.

## Font Rotation Strategy

Even with favorites identified, occasional rotation prevents visual staleness:

```bash
font-sync random  # Rotate through favorites
```

Change fonts weekly, monthly, or whenever the current font feels stale. Rotation maintains freshness without constant searching for "something better."

## Success Metrics

The workflow succeeds when:

- Font choice takes 10 seconds, not 10 minutes
- Naming 3 favorite fonts happens without thinking
- Worrying about "missing out" on the perfect font stops
- code_fonts directory contains <10 font families
- new_fonts directory is archived
- Feeling lighter and less overwhelmed

## Troubleshooting

**Font doesn't apply**: Restart Ghostty after changes. Terminal emulators cache font choices.

**Icons show as boxes**: Using non-Nerd Font. Apply a font with "Nerd Font" in the name.

**Icons too small**: Using Mono variant. Try default variant (without "Mono" suffix).

**Text alignment broken**: Using Propo variant in terminal. Switch to Mono or default variant.

**Font looks blurry**: Check font-thicken setting in Ghostty config. May need adjustment.

**Ligatures not working**: Remove or comment out `font-feature = -liga` in Ghostty config.

## Related Workflows

**Theme Customization**: Similar systematic approach to testing and curating color themes. See [Theme Customization](themes.md).

**Tool Discovery**: Finding and evaluating development tools. See [Tool Discovery](tool-discovery.md).

**Backup**: Maintaining dotfiles and configurations. See [Backup](backup.md).

## Further Reading

- [Nerd Fonts Explained](../reference/fonts/nerd-fonts-explained.md) - Understanding variants
- [Font Weights and Variants](../reference/fonts/font-weights-and-variants.md) - When to use Bold/Italic
- [Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md) - Why monospace matters
- [Font Comparison](../reference/fonts/font-comparison.md) - Detailed comparisons of your collection

---

**Start here**: `font-sync adventure` to begin testing immediately. Or `font-sync preview` to choose the first font interactively. Either way, start testing rather than researching endlessly.
