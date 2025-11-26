# Font Weights and Variants

Understanding when and why to use Bold, Italic, Light, and other font variants in coding and terminal environments.

## Font Weight Scale

Fonts use a standardized weight scale from 100 (thinnest) to 900 (thickest):

| Weight Value | Name | Common Use |
|--------------|------|------------|
| 100 | Thin / Hairline | Rarely used in code |
| 200 | Extra Light / Ultra Light | Minimal use |
| 300 | Light | Subtle, less prominent text |
| 400 | **Regular / Normal** | **Standard for code** |
| 500 | Medium | Slightly emphasized |
| 600 | Semi Bold / Demi Bold | Headings, emphasis |
| 700 | Bold | **Strong emphasis** |
| 800 | Extra Bold / Ultra Bold | Maximum emphasis |
| 900 | Black / Heavy | Rarely used in code |

## Why Multiple Weights Exist

Font families include multiple weights for **visual hierarchy and emphasis**, not for everyday coding. However, terminals and editors use them for specific purposes.

## Font Variants in Terminal/Code Editors

### Regular (400) - Your Daily Driver

**What it is**:

- The default, standard weight
- Optimized for extended reading
- Most of your code appears in this weight

**When it's used**:

- 95% of all code
- Normal text in terminal
- Default editor text
- File contents, logs, output

**Why it matters**:

- This is what you'll stare at for hours
- Must be comfortable and not strain eyes
- Not too thin, not too bold

### Bold (700) - Syntax Highlighting

**What it is**:

- Thicker, heavier characters
- Creates visual contrast
- Draws attention

**When it's used**:

- **Syntax highlighting** - Keywords (if, for, def, class)
- **Errors and warnings** in terminal output
- **Matched search results** in editor
- **Current line number** in some themes
- **Active selections** in some UIs
- **Headers** in markdown/documentation

**Examples in code**:

```python
def function_name():  # 'def' often rendered in bold
    if condition:     # 'if' often rendered in bold
        return True   # 'return' often rendered in bold
```text

**Why it matters**:

- Makes keywords stand out
- Helps scan code quickly
- Creates visual structure

**Terminal example**:

```

ERROR: File not found   # ERROR in bold
Warning: Deprecated     # Warning in bold

```text

### Italic (Normal weight, slanted)

**What it is**:

- Slanted version of regular weight
- Same thickness, different angle
- Creates visual distinction without weight change

**When it's used**:

- **Comments** in code (very common)
- **Docstrings** in some themes
- **Emphasis** in markdown
- **Variable names** in some themes
- **String literals** in some color schemes
- **Parameters** in some themes

**Examples in code**:

```python
# This comment appears in italic
def function(param):    # 'param' might be italic
    """Docstring text might be italic"""
    variable = "string might be italic"
```

**Why it matters**:

- Distinguishes comments from code
- Makes documentation stand out
- Reduces visual weight of secondary text

### Bold Italic - Rare Combination

**What it is**:

- Both bold AND italic
- Maximum emphasis
- Heavy and slanted

**When it's used**:

- **Very rarely** in code
- Some themes use for specific highlighting
- Markdown **_bold italic text_**
- Occasionally for special keywords

**Why it exists**:

- Maximum distinction when needed
- Flexibility for theme designers
- Completeness of font family

## Font Weights Beyond Bold

### Light (300) - Subtle Use

**What it is**:

- Thinner than regular
- Less visual weight
- More delicate appearance

**When it's used**:

- Rarely in coding
- Sometimes for de-emphasized text
- UI elements like line numbers
- Background/secondary information

**Why it exists**:

- Visual hierarchy
- De-emphasize less important text
- Some people prefer lighter for less eye strain

**Practical use**:

- **Line numbers** (lighter than code)
- **Status bar** text
- **Grayed-out/disabled** items

### Semi Bold (600) - Middle Ground

**What it is**:

- Between Regular (400) and Bold (700)
- Noticeable but not heavy

**When it's used**:

- Instead of Bold in some themes
- Headings in documentation
- Slightly emphasized keywords

**Why it exists**:

- Bold might be too heavy
- Regular not enough contrast
- Fine-tuning visual hierarchy

### Extra Bold (800) / Black (900) - Extreme Emphasis

**What it is**:

- Heavier than Bold
- Maximum visual weight
- Very thick characters

**When it's used**:

- Rarely in coding environments
- Maybe for critical errors
- Headlines or branding
- ASCII art

**Why it exists**:

- Completeness of font family
- Graphic design use
- Maximum possible emphasis

## What You Actually Need for Coding

### Minimum: Regular Only

**You can code with just Regular weight.**

- Most themes use only color for differentiation
- Bold is nice to have, not required
- Italic is common but optional

### Recommended: Regular + Bold + Italic + Bold Italic

**This covers 99% of syntax highlighting needs.**

- Regular: 90% of code
- Bold: Keywords and emphasis
- Italic: Comments and docstrings
- Bold Italic: Special cases

### Avoid: Light, Extra Light, Semi Bold, Extra Bold, Black

**You probably don't need these for coding.**

- They take up space
- Rarely used by themes
- Regular/Bold/Italic is enough

## How Themes Use Font Weights

### Typical Syntax Highlighting

**Neovim/Vim themes**:

- Keywords: `gui=bold` → Uses Bold weight
- Comments: `gui=italic` → Uses Italic
- Strings: `guifg=#color` → Regular, just colored
- Functions: `gui=bold` or just colored

**VS Code themes**:

- Similar pattern
- JSON theme defines `fontStyle`
- `"fontStyle": "bold"` or `"fontStyle": "italic"`

### Terminal Emulator Rendering

**ANSI escape codes**:

```bash
echo -e "\e[1mBold text\e[0m"      # Requests bold
echo -e "\e[3mItalic text\e[0m"    # Requests italic
echo -e "\e[1;3mBoth\e[0m"         # Requests both
```text

**What actually happens**:

- Terminal looks for Bold weight in font
- Falls back to synthetic bold if missing
- Uses Italic variant if available
- Synthetic italic if missing

## Synthetic vs True Bold/Italic

### True Bold/Italic

- Font designer created proper variants
- Optimized spacing and proportions
- Better looking, more readable

### Synthetic Bold/Italic

- Terminal/editor makes regular weight "bold" by thickening
- Makes regular "italic" by slanting
- Looks worse, can blur or look distorted

**Why it matters**:

- Some fonts don't include all weights
- Terminal might fake it
- True variants always look better

**Check if font has true variants**:

```bash
fc-list | grep "FiraCode.*Bold"
fc-list | grep "FiraCode.*Italic"
```

## Font Family Completeness

### Minimal Font Family

```text
FontName-Regular.otf
```

**Just one weight.** Terminal will synthesize bold/italic.

### Standard Font Family

```text
FontName-Regular.otf
FontName-Bold.otf
FontName-Italic.otf
FontName-BoldItalic.otf
```

**Four variants.** Covers all common use cases.

### Complete Font Family

```text
FontName-Thin.otf
FontName-Light.otf
FontName-Regular.otf
FontName-Medium.otf
FontName-SemiBold.otf
FontName-Bold.otf
FontName-ExtraBold.otf
FontName-Black.otf
(+ all italic variants)
```

**16+ files.** Maximum flexibility.

## Do You Need All Weights?

### No

**For terminal and coding**:

- Install: Regular, Bold, Italic, Bold Italic
- Skip: Everything else

**Storage savings**:

- Each font file: 200KB - 2MB
- Skip 10 weights: Save 5-20MB per family
- Multiply by 20 fonts: Save 100-400MB

**Practical benefit**:

- Faster font selection menus
- Less clutter
- Easier to find what you need

## Enabling Bold and Italic in Terminals

### Neovim/Vim

**Set terminal to support styles**:

```vim
set termguicolors  " Use GUI colors in terminal
```text

**Theme uses**:

```vim
highlight Keyword gui=bold
highlight Comment gui=italic
```

**Font must have**:

- Bold weight file
- Italic weight file

### Ghostty

Ghostty automatically uses Bold/Italic variants if font has them.

**Your config** (`~/.config/ghostty/config`):

```text
font-family = "FiraCode Nerd Font"
```

Ghostty will use:

- `FiraCode Nerd Font Regular` for normal text
- `FiraCode Nerd Font Bold` for bold
- `FiraCode Nerd Font Italic` for italic

No additional config needed.

### iTerm2

**Preferences → Profiles → Text**:

- Font: Select your Nerd Font
- Check "Use built-in Powerline glyphs" (optional)
- Bold and Italic work automatically if font has them

### Alacritty

**Config** (`~/.config/alacritty/alacritty.yml`):

```yaml
font:
  normal:
    family: "FiraCode Nerd Font"
    style: Regular
  bold:
    family: "FiraCode Nerd Font"
    style: Bold
  italic:
    family: "FiraCode Nerd Font"
    style: Italic
```text

Can explicitly set which weight to use for each style.

## When Different Weights Matter

### Retina/HiDPI Displays

**High resolution screens**:

- Regular weight may look too thin
- Consider Medium (500) or Retina weight
- Some fonts offer "Retina" variant (e.g., FiraCode Retina)

**Example**: FiraCode offers:

- Regular (400)
- Retina (450) - Slightly heavier for high-DPI
- Medium (500)
- Bold (700)

**When to use**:

- Regular looks too spindly on Retina display → Try Retina weight
- Still too thin → Try Medium

### Low Resolution / Small Sizes

**Font size 10-12 on non-Retina**:

- Regular might look too heavy
- Light (300) might be better
- Or increase font size instead

### Personal Preference

**Some developers prefer**:

- Lighter weights for less visual weight
- Medium weights for better distinction
- Bold for everything (rare)

**Experiment**:

```bash
font-sync apply "FiraCode Nerd Font"  # Regular
# Try different weights in your theme/terminal settings
```

## Font Weight in Practice

### Example: Source Code Pro

**Available weights**:

- Extra Light (200)
- Light (300)
- Regular (400)
- Medium (500)
- Semibold (600)
- Bold (700)
- Black (900)

**What you install**:

- Regular - for 90% of code
- Bold - for keywords
- Italic - for comments
- Bold Italic - for completeness

**What you skip**:

- Extra Light, Light, Medium, Semibold, Black

**Result**:

- 4 files instead of 14+
- Still get full syntax highlighting
- Save disk space

## Configuring Font Weight Preferences

### VS Code

**settings.json**:

```json
{
  "editor.fontFamily": "FiraCode Nerd Font",
  "editor.fontLigatures": true,
  "editor.fontSize": 14,
  "editor.fontWeight": "400",     // Normal weight
  "editor.fontWeight": "500",     // Try medium for sharper look
}
```text

### Neovim

**Using guifont**:

```lua
vim.o.guifont = "FiraCode Nerd Font:h14:w500"  -- Medium weight
```

### Terminal (varies)

Most terminals don't let you choose weight for normal text - they use Regular. Bold is automatic when ANSI codes request it.

## Summary

### What Font Weights Are For

**Regular (400)**: Default text, 90% of coding
**Bold (700)**: Keywords, emphasis, errors
**Italic**: Comments, docstrings, parameters
**Bold Italic**: Special highlighting

### What You Need

**Essential**: Regular
**Recommended**: Regular + Bold + Italic + Bold Italic
**Optional**: Light, Medium, Retina (for specific use cases)
**Skip**: Extra Light, Semi Bold, Extra Bold, Black

### How to Use Them

1. Install full font family or just Regular/Bold/Italic
2. Terminal/editor automatically uses them for syntax highlighting
3. No manual configuration needed in most cases
4. Themes control when bold/italic appear

### Decision Guide

**Too thin?** → Try Medium or Retina weight
**Too thick?** → Try Light weight or increase font size
**Not sure?** → Start with Regular, it's designed for this
**Want contrast?** → Make sure Bold and Italic are installed

---

**TL;DR**: For coding, you only need **Regular, Bold, Italic, and Bold Italic** font files. Everything else is optional. Your terminal and editor will use these automatically for syntax highlighting without any special configuration.

## Related Documentation

- [Nerd Fonts Explained](nerd-fonts-explained.md) - Understanding Nerd Font variants
- [Terminal Fonts Guide](terminal-fonts-guide.md) - Why monospace matters
- [Font Comparison](font-comparison.md) - Compare fonts in your collection
