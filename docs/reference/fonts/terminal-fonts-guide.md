# Terminal Fonts Guide

Understanding why terminal emulators require monospace fonts and whether proportional fonts from your collection can be used.

## The Core Requirement: Monospace Fonts

Terminal emulators are built on the assumption that every character occupies the same fixed width. This isn't a limitation - it's fundamental to how terminals work.

## Why Terminals Need Monospace

### Historical Context

Terminals evolved from physical teletypewriters and video display terminals (VDTs) where characters were:

- Fixed in grid positions
- One character per cell
- Physically unable to vary width

Modern terminal emulators inherit this design because:

- Decades of Unix software assume monospace
- Terminal protocols (ANSI/VT100) define positions by column/row
- Too much existing software depends on it

### Technical Requirements

**Grid-based positioning**:

```text
Column:  1    2    3    4    5
         ┌────┬────┬────┬────┬────┐
         │ t  │ e  │ s  │ t  │    │
         └────┴────┴────┴────┴────┘
```

Every character must align to this grid. Applications position text by column number, not pixel position.

### What Breaks with Proportional Fonts

**Column alignment fails**:

```text
Monospace (works):
Column:  1    2    3    4    5    6    7    8
         i    s    o    l    a    t    e    d

Proportional (breaks):
         i s  o  l   a  t   e  d
Column:  1 2  3  4   5  6   7  8  (doesn't match)
```

The 'i' is narrower than 'w', breaking column calculations.

**Applications that break**:

- `ls` column output
- `top` and system monitors
- `vim` and `emacs` (cursor positioning)
- `tmux` and screen multiplexers
- Any TUI application
- Tab-aligned data
- ASCII art
- Box-drawing characters

## Can Any Terminal Use Proportional Fonts?

### Rare Exceptions

A few specialized terminals attempt proportional font support:

**mlterm**:

- Experimental proportional font support
- Adjusts terminal grid dynamically
- Many applications still break

**ConEmu** (Windows):

- Can use proportional fonts
- Limited compatibility with terminal applications

**Visual Studio Code integrated terminal**:

- Can technically use proportional fonts
- Not recommended, breaks many tools

### Why Even Modern Terminals Stay Monospace

Modern terminals like Ghostty, Alacritty, and kitty stick with monospace because:

- Compatibility with all terminal software
- Standard terminal protocols expect it
- Nerd Font icons work correctly
- TUI applications render properly
- No edge cases or broken layouts

## Can You Use Fonts from new_fonts/?

**Short answer: No, not for terminal use.**

### Why Not

Fonts in your `new_fonts/` directory (1,595 fonts) are likely:

- **Proportional** fonts for graphic design
- **Display** fonts for headings
- **Script** or handwriting fonts
- **Decorative** fonts for specific uses

**None of these are appropriate for terminals.**

### What Those Fonts Are For

**Proportional sans-serif** (Helvetica, Arial, Roboto):

- UI design
- Websites
- Documents
- Presentations

**Proportional serif** (Times, Georgia, Merriweather):

- Books
- Articles
- Long-form reading
- Print materials

**Display fonts** (Impact, Bebas, various decorative):

- Logos
- Headers
- Posters
- Branding

**Script/Handwriting** (Various cursive styles):

- Invitations
- Greeting cards
- Decorative text

**Decorative/Novelty**:

- Special projects
- Themed designs
- One-off graphics

### Could Any Be Converted?

**Theoretically**: Some proportional fonts could be "converted" to monospace by adjusting character widths.

**Practically**:

1. This is a complex font editing task
2. Results usually look bad (too wide or too narrow)
3. Existing monospace code fonts are already optimized
4. Not worth the effort

## What About Propo Nerd Fonts?

You might notice **Nerd Font Propo** variants exist. These are different.

### Nerd Font Propo Characteristics

**Semi-proportional**:

- Regular characters have variable widths
- Icons maintain monospace width
- Still not suitable for terminal use

**Intended for**:

- GUI applications with icon support
- Documents needing Nerd Font icons
- Presentations
- Non-terminal contexts

**Not for terminals** because:

- Code alignment breaks
- Column-based tools fail
- TUI applications render incorrectly

**Note**: For comic-style fonts that work in both Ghostty and Kitty, use `ComicMonoNF` (xtevenx v1) or `ComicShannsMono Nerd Font Mono`. See [Font Terminal Compatibility](../../learnings/font-terminal-compatibility.md) for details on why some fonts work in one terminal but not another.

## Monospace Font Characteristics

### Fixed Width

Every character has identical advance width:

```text
Width in cells:
'i' = 1 cell
'm' = 1 cell
'W' = 1 cell
' ' = 1 cell
```

### Visual Compensation

Monospace fonts **visually balance** characters despite fixed width:

**Narrow characters** (i, l, 1):

- Add space around them
- Keep glyph width fixed

**Wide characters** (m, w, W):

- Condense slightly
- Stay within fixed width

**Result**: Readable text with perfect alignment

### Design Trade-offs

**Compared to proportional fonts**:

- Less efficient use of space
- Can look "loose" or "tight"
- Optimized for code, not prose
- Prioritize clarity over aesthetics

## Identifying Monospace Fonts

### Check with fc-list

```bash
# List monospace fonts
fc-list :spacing=mono family

# Check if specific font is monospace
fc-list "FiraCode" | grep spacing
```text

### Visual Test

**Type this**:

```

iiiiiiiiii
mmmmmmmmmm

```text

**Monospace**: Both lines same length
**Proportional**: 'mmm' line much longer

### Font Naming Hints

**Usually monospace**:

- Contains "Mono" in name
- Contains "Code" in name
- "Console", "Terminal", "Typewriter"
- "Courier", "Menlo", "Monaco"

**Usually proportional**:

- "Sans", "Serif" without "Mono"
- "Text", "Display", "Book"
- Famous UI fonts (Helvetica, Arial, Roboto)

## Exceptions and Edge Cases

### Variable-Width Glyphs in Nerd Fonts

**Nerd Font (default variant)**:

- Regular characters: Monospace
- Icons: Can extend 1.5-2 cells visually
- Still works because "advance width" stays 1 cell

**This is different** from proportional fonts:

- Proportional: advance width varies
- Nerd Fonts: visual width varies, advance stays fixed

### Fonts Claiming to Be "Monospace" But Aren't

Some fonts say "Mono" but aren't truly monospace:

- May have variable-width diacritics
- Italic variants sometimes proportional
- Ligatures change effective width

**Test before trusting** the name.

## What You Can Do With new_fonts/

### Archive Them

**Realistic use cases**:

- Maybe 5-10 for graphic design projects
- Zero for terminal/coding

### Keep Select Fonts for Other Uses

**If you do graphic design**:

- Keep 20-30 carefully chosen fonts
- Archive the rest
- Organize by category

**If you don't do graphic design**:

- Archive everything
- Download specific fonts when needed
- Save 710MB of disk space

### Make Peace with Not Using Them

**Hard truth**:

- You've had 1,595 fonts
- Haven't used them in 40 years
- Won't start using them now
- They're clutter, not assets

**Better approach**:

1. Archive everything
2. When you need a font, search online
3. Download that specific font
4. Use it for that project
5. Don't hoard "just in case"

## Best Practices for Terminal Fonts

### Choose Proper Monospace

**Start with proven fonts**:

- FiraCode Nerd Font
- JetBrains Mono Nerd Font
- Hack Nerd Font
- Iosevka Nerd Font
- Source Code Pro Nerd Font

**All are**:

- True monospace
- Designed for code
- Have Nerd Font variants
- Well-tested in terminals

### Verify Monospace

**Before committing**:

```bash
# Check font spacing
fc-list "Font Name" | grep spacing

# Should show: spacing=100 (mono)
# Not: spacing=0 (proportional)
```

### Test in Real Use

**Don't judge by**:

- How it looks in a preview
- How it looks in one line of text

**Judge by**:

- Real code files
- Running `ls -la`
- Opening `vim` or `neovim`
- Running `tmux`
- Actual terminal use for a week

## Font Recommendations by Use Case

### Pure Terminal Work

**Priority**: Perfect monospace, good distinction

- Hack Nerd Font Mono
- Source Code Pro Nerd Font
- JetBrains Mono Nerd Font Mono

### Terminal + Ligatures

**Priority**: Ligatures + monospace

- FiraCode Nerd Font
- JetBrains Mono Nerd Font
- Cascadia Code Nerd Font

### Maximum Code Density

**Priority**: Narrow, fits more code

- Iosevka Nerd Font Mono
- Iosevka Term Nerd Font

### Comfortable Long Sessions

**Priority**: Readability, less eye strain

- JetBrains Mono Nerd Font
- Source Code Pro Nerd Font
- Meslo Nerd Font

### Fun/Personality

**Priority**: Comic sans style, casual

- ComicShannsMono Nerd Font
- ComicMonoNF (xtevenx v1 - works in both Ghostty and Kitty)

## Converting a Proportional Font (Don't Do This)

**Theoretical process**:

1. Open font in FontForge
2. Measure widest character
3. Set all glyphs to that width
4. Adjust spacing
5. Save as new font

**Why this is bad**:

- Narrow characters too wide (i, l, 1)
- Wide characters too narrow (m, w, W)
- Looks awkward and unbalanced
- Defeats purpose of the original font
- Existing monospace fonts are better

**Better approach**:

- Use fonts designed for monospace
- Don't try to convert proportional fonts

## Terminal Font Rendering

### Antialiasing

**What it is**: Smoothing of font edges

**Affects**:

- How crisp text appears
- Readability at small sizes

**Your Ghostty config** shows:

```text
font-thicken = false
```

This keeps fonts thin and crisp.

### Ligatures

**What they are**: Multiple characters combined into one glyph

**Examples**:

- `=>` becomes →
- `!=` becomes ≠
- `===` becomes ≡

**Your config**:

```text
font-feature = -liga  # Disable ligatures
```

You have ligatures disabled. To enable:

```text
# Remove or comment out the -liga line
# font-feature = -liga
```

### Hinting

**What it is**: Instructions for rendering at small sizes

**Affects**:

- Clarity at 12-14pt sizes
- Pixel grid alignment

**Modern fonts** have good hinting. Trust them.

## Summary

### Can You Use new_fonts/ in Terminal?

**No.** They're proportional fonts for graphic design, not terminal use.

### Why Not?

Terminals require monospace fonts for:

- Column alignment
- TUI applications
- Cursor positioning
- ASCII art
- Tab alignment
- Box-drawing characters

### What Are Those Fonts For?

- Graphic design
- Web design
- Print materials
- Documents
- Presentations

**Not for code or terminals.**

### What Should You Do?

1. **Archive new_fonts/** (see workflow guide)
2. **Use proper monospace Nerd Fonts** for terminal
3. **If you need a decorative font**, download it specifically
4. **Stop hoarding fonts** you'll never use

### What Fonts Work in Terminals?

**Only monospace fonts**, specifically:

- Font family name includes "Mono"
- Designed for code/terminal use
- Nerd Font patched variants
- Verified with `fc-list` spacing=mono

**Your code_fonts/** directory has proper fonts.
**Your new_fonts/** directory does not.

---

**TL;DR**: Terminals need monospace fonts due to their grid-based design. The 1,595 fonts in `new_fonts/` are proportional fonts for graphic design and won't work in terminal emulators. Use the fonts in `code_fonts/` - they're designed for this. Archive everything in `new_fonts/` unless you actually do graphic design work.

## Related Documentation

- [Nerd Fonts Explained](nerd-fonts-explained.md) - Understanding Nerd Font variants
- [Font Weights and Variants](font-weights-and-variants.md) - When to use Bold, Italic, etc.
- [Font Comparison](font-comparison.md) - Compare fonts in your collection
