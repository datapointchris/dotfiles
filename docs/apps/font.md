# Font Tool

Automatic font tracking with data-driven rankings. Every time you apply, like, dislike, or note a font, it's logged. Rankings emerge from your actual usage patterns.

## Quick Start

```bash
font change          # Interactive picker with previews
font like "reason"   # Like current font
font dislike         # Dislike without message
font note "text"     # Add note to current font
font rank            # See rankings
font log             # View history
```

## Commands

### Viewing

- `font current` - Show active font
- `font list` - List available fonts
- `font rank` - Font rankings by likes/dislikes
- `font log` - View complete history with file locations

### Applying Fonts

- `font change` - Interactive picker with previews (fzf + image previews)
- `font apply <font>` - Apply by name (auto-logs)
- `font random` - Random from all fonts

### Tracking

- `font like [message]` - Like current font with optional reason
- `font dislike [message]` - Dislike current font with optional reason
- `font note <message>` - Add note to current font (message required)
- `font reject <message>` - Reject current font with reason (hides from lists)
- `font rejected` - Show all rejected fonts with reasons

All tracking actions automatically log to per-platform history files. Rejected fonts are hidden from `font list` and the interactive picker to avoid rediscovery.

### Utilities

- `font generate-previews` - Pre-generate all preview images for instant browsing
- `font clear-cache` - Clear preview image cache

## Data & History

Font history is stored in per-platform JSONL files within the app directory:

```text
apps/common/font/data/
├── history-macos.jsonl
├── history-arch.jsonl
├── history-wsl.jsonl
└── rejected-fonts.json
```

**Zero merge conflicts:** Each platform only writes to its own file. When you pull/push across machines, there are no conflicts.

**Cross-platform rankings:** `font rank` combines data from all platforms to show fonts you like across all your machines.

**Auto-recovery:** If you delete history files, they're automatically recreated on next use.

View file locations with `font log`.

## How It Works

Each action appends a timestamped JSON record (in UTC):

```json
{"ts":"2025-11-26T17:24:03+00:00","platform":"macos","font":"Fira Code","action":"like","message":"Great ligatures"}
```

Rankings aggregate likes/dislikes to calculate scores:

```text
Score = (total likes) - (total dislikes)
```

Fonts are then sorted by score descending, then by last usage date.

## Workflow

Start testing a new font:

```bash
font change                           # Pick a font interactively
# Use it for actual work
font like "Good weight"               # Like it
font note "Works well for prose"     # Add observations
```

After testing several fonts:

```bash
font rank                             # See your favorites
```

Switch to a random font:

```bash
font random                           # Try something new
```

## See Also

- [Nerd Fonts Explained](../reference/fonts/nerd-fonts-explained.md) - What Nerd Fonts are and why they matter
- [Font Weights and Variants](../reference/fonts/font-weights-and-variants.md) - Understanding Bold/Italic/Light variants
- [Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md) - Why monospace matters for terminals
- [Font Comparison](../reference/fonts/font-comparison.md) - Detailed comparison of font families
