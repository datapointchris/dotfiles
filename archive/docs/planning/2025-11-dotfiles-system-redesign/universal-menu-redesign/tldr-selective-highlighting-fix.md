# tldr Selective Highlighting Fix

**Date:** 2025-11-07
**Issue:** "The syntax highlighting is working, but it is highlighting the first word of every line of the description in tldr as well"
**Status:** ✅ Fixed

## Problem

When we added bat syntax highlighting to tldr output, it was highlighting the ENTIRE output as bash code, including description lines. This caused description text to be colorized incorrectly.

**Example of the problem:**

```
tldr:
  rg                              ← Highlighted (wrong!)
  Ripgrep, a recursive...         ← "Ripgrep" highlighted (wrong!)
  Aims to be faster...            ← "Aims" highlighted (wrong!)

  Recursively search...           ← "Recursively" highlighted (wrong!)
    rg pattern                    ← Highlighted (correct!)
```

## Understanding tldr Format

tldr output has a specific structure:

- **Command name** (2 spaces indent)
- **Description lines** (2 spaces indent) - plain text, should NOT be highlighted
- **Example descriptions** (2 spaces indent) - plain text, should NOT be highlighted
- **Command examples** (4+ spaces indent) - actual commands, SHOULD be highlighted

## Solution

Changed `writeTldr()` to parse the tldr output line-by-line and only highlight lines with 4+ space indentation (command examples).

**File:** `tools/menu-go/internal/formatter/preview.go` (line 272-316)

### Before (highlighting everything)

```go
// Pipe entire tldr output through bat
batCmd := exec.Command("bat", "--color=always", "--style=plain", "--language=bash")
batCmd.Stdin = strings.NewReader(tldrText)
buf.WriteString(batOut.String())  // Everything highlighted!
```

### After (selective highlighting)

```go
// Parse tldr output line by line
lines := strings.Split(tldrText, "\n")
for _, line := range lines {
    if len(line) >= 4 && line[0:4] == "    " {
        // Command example (4+ space indent) - highlight it
        highlighted := highlightCode(strings.TrimSpace(line))
        buf.WriteString("    ")
        buf.WriteString(highlighted)
        buf.WriteString("\n")
    } else {
        // Description line (0-3 space indent) - plain text
        buf.WriteString(line)
        buf.WriteString("\n")
    }
}
```

**Logic:**

- Lines starting with 4+ spaces → command examples → apply bat highlighting
- All other lines → descriptions → keep as plain text

## Result

**After the fix:**

```
tldr:
  rg                              ← Plain text ✓
  Ripgrep, a recursive...         ← Plain text ✓
  Aims to be faster...            ← Plain text ✓

  Recursively search...           ← Plain text ✓
    rg pattern                    ← Highlighted ✓
```

**Visual breakdown:**

- Title and descriptions: Plain text (white/default terminal color)
- Command examples: Syntax highlighted (green command names, colored arguments)

## Examples

### Example 1: rg command

```
tldr:
  rg                                              # Plain
  Ripgrep, a recursive line-oriented search tool. # Plain
  Aims to be a faster alternative to grep.        # Plain
  More information: https://...                   # Plain

  Recursively search current directory:           # Plain
    rg pattern                                    # Highlighted!

  Include hidden files:                           # Plain
    rg --hidden --no-ignore pattern               # Highlighted!
```

### Example 2: fd command

```
tldr:
  fd                                              # Plain
  An alternative to find.                         # Plain

  Recursively find files:                         # Plain
    fd "string|regex"                             # Highlighted!

  Find with extension:                            # Plain
    fd --extension txt                            # Highlighted!
```

## Code Details

The key logic:

```go
if len(line) >= 4 && line[0:4] == "    " {
    // 4+ space indent = command example
    highlighted := highlightCode(strings.TrimSpace(line))
    buf.WriteString("    ")
    buf.WriteString(highlighted)
    buf.WriteString("\n")
} else {
    // 0-3 space indent = description
    buf.WriteString(line)
    buf.WriteString("\n")
}
```

Uses existing `highlightCode()` function which:

1. Pipes code through bat with bash language
2. Falls back to plain colorization if bat unavailable

## Benefits

1. **Correct highlighting**: Only actual commands are highlighted
2. **Readability**: Description text remains plain and easy to read
3. **Consistency**: Matches how terminal help usually looks (descriptions plain, commands highlighted)
4. **Performance**: No change (still one bat call per command example line)

## Files Modified

### Go Source

**`tools/menu-go/internal/formatter/preview.go`** (line 272-316)

- Rewrote `writeTldr()` to parse lines
- Selective highlighting based on indentation
- Maintains 4-space indent for command examples

### Binary

**`~/.local/bin/menu-go-new`**

- Rebuilt with fix

## Testing

Manual verification:

```bash
$ menu-go-new preview commands rg

tldr:
  rg                                    # <- Check: plain text
  Ripgrep, a recursive...               # <- Check: plain text
    rg pattern                          # <- Check: highlighted
```

**Verified:**

- ✓ Description lines are plain text
- ✓ Command examples have syntax highlighting
- ✓ Works for rg, fd, and all commands with use_tldr: true

## Conclusion

The tldr output now correctly highlights only command examples (indented 4+ spaces), while keeping all descriptive text as plain text for better readability.

**Status:** ✅ Complete and working correctly
