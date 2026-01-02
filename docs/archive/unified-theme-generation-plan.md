# Unified Theme Generation System - Analysis & Implementation Plan

> **STATUS: ✅ COMPLETE** (2024-12-30)
>
> This plan has been fully implemented. The unified theme system is operational with 39 themes, 16 generators, and a complete CLI. See "Final Status" section at the end for details.
>
> **Archived to:** `.planning/archive/`

## Executive Summary

This plan addresses creating a unified theme generation system that can:
1. Generate consistent themes for ALL applications from a source palette
2. Generate complete Neovim colorschemes with comprehensive highlight coverage
3. Support multiple "interpretations" of the same theme (base16-gruvbox, ghostty-gruvbox, neovim-gruvbox)
4. Eventually expand to VSCode for work environment consistency

### Key Principles

1. **Additive Only**: All new infrastructure is ADDITIONAL. Existing `theme-sync`, `library/`, and other systems remain untouched until the new system is fully validated and in use.

2. **Flat Directory Structure**: Theme variants are top-level for easy discovery:
   - `themes/gruvbox-dark-hard-base16/`
   - `themes/gruvbox-dark-hard-ghostty/`
   - `themes/gruvbox-dark-hard-neovim/`

3. **Single Theme First**: Complete all phases with gruvbox only. Learn and iterate before expanding to other themes.

4. **Deprecation Note**: `theme-sync` is deprecated and will be replaced by `theme`. New infrastructure builds toward this replacement.

---

## Part 1: Research Findings

### Why Neovim Colorschemes Are So Different

#### Historical Context

Neovim colorschemes evolved from Vim's VimScript era to Lua, with no enforced standard:

1. **VimScript Era (pre-2015)**: `highlight` commands, no structure
2. **Lua Transition (2019-2021)**: Direct `nvim_set_hl()` calls, varied approaches
3. **Treesitter Era (2021+)**: New `@capture` groups, semantic tokens from LSP
4. **Framework Era (2022+)**: Lush, nvim-highlite, mini.colors emerged

#### Why No Standard Exists

- **Vim Compatibility**: Many colorschemes maintain Vim compatibility
- **Plugin Diversity**: Each plugin defines custom highlight groups
- **Personal Preference**: Some prefer palette-first, others semantic-first
- **Performance Tradeoffs**: Compilation, lazy loading, linking strategies differ
- **LSP/Treesitter Evolution**: Rapid API changes required adaptations

Sources:
- [Build Your Own Neovim Colorscheme in Lua](https://medium.com/@ronxvier/build-your-own-neovim-colorscheme-in-lua-3b01adf019e0)
- [Neovim Colorscheme Discussion](https://github.com/neovim/neovim/discussions/28850)

### Neovim Highlight Group Categories

A complete Neovim colorscheme must cover:

| Category | Count | Examples |
|----------|-------|----------|
| Editor UI | ~50 | Normal, CursorLine, StatusLine, Pmenu |
| Vim Syntax | ~20 | Comment, String, Function, Keyword |
| Treesitter | ~60 | @function, @variable, @keyword, @string |
| LSP Semantic | ~30 | @lsp.type.function, @lsp.mod.readonly |
| Diagnostics | ~15 | DiagnosticError, DiagnosticHint |
| Git/Diff | ~10 | DiffAdd, GitSignsAdd |
| Plugin-specific | 100+ | Telescope*, NeoTree*, Cmp*, etc. |

**Total for comprehensive coverage: 200-400 highlight groups**

The kanagawa.nvim colorscheme (~52,000 bytes) has comprehensive coverage.
Simpler themes (~5,000 bytes) cover only basics.

Sources:
- [Neovim :h highlight](https://neovim.io/doc/user/syntax.html#highlight)
- [Treesitter Highlight Groups](https://neovim.io/doc/user/treesitter.html)

### Cross-Editor Theme Approaches

#### Base16 / Tinted-Theming

**How it works:**
1. Define a scheme (16 colors in YAML)
2. Templates (mustache files) map colors to app-specific syntax
3. Builder renders templates → app configs

**Pros:**
- 230+ schemes, 70+ apps supported
- Single source of truth
- Tinty CLI for management

**Cons:**
- Only 16 colors limits expressiveness
- Neovim template coverage is basic (~100 groups)
- No semantic tokens, limited treesitter support

Sources:
- [tinted-theming/home](https://github.com/tinted-theming/home)
- [tinted-theming/tinty](https://github.com/tinted-theming/tinty)

#### Themer (mjswensen/themer)

**How it works:**
1. Define colors in JavaScript
2. Plugins generate output for each app (VSCode, Vim, terminals, wallpapers)
3. Can import base16 YAML as input

**Pros:**
- Programmatic color manipulation
- Good VSCode support
- Wallpaper generation

**Cons:**
- Node.js dependency
- Less comprehensive than base16 for terminal apps
- Vim template is basic

Sources:
- [themer.dev](https://themer.dev/)
- [mjswensen/themer](https://github.com/mjswensen/themer)

#### Catppuccin's Approach

**How it works:**
1. Single palette (26 named colors) with 4 flavor variants
2. Style guide defines semantic mappings for each app type
3. 442 individual ports, each hand-maintained
4. Automation for port listing/README generation only

**Pros:**
- Highest quality ports
- Consistent visual language
- Comprehensive coverage (editors, terminals, websites, apps)

**Cons:**
- Manual maintenance burden (staff team required)
- Not template-based - each port is custom code
- Not easily reproducible for personal themes

Sources:
- [Catppuccin Style Guide](https://github.com/catppuccin/catppuccin/blob/main/docs/style-guide.md)
- [Catppuccin Ports](https://catppuccin.com/ports/)

#### TokyoNight's Approach

**How it works:**
1. Comprehensive Neovim colorscheme with full highlight coverage
2. `extras/` folder with generated configs for terminals
3. Simple template system (`lua/tokyonight/extra/*.lua`)
4. Build script generates extras from palette

**Pros:**
- Neovim-first with export capability
- Good terminal coverage
- Single source maintained in Neovim plugin

**Cons:**
- VSCode port is separate project
- Not easily extensible to new apps
- Tightly coupled to tokyonight structure

Sources:
- [folke/tokyonight.nvim](https://github.com/folke/tokyonight.nvim)

### VSCode Theme Architecture

VSCode themes use TextMate scopes, a different semantic model than Neovim:

```json
{
  "type": "dark",
  "colors": {
    "editor.background": "#1e1e1e",
    "editor.foreground": "#d4d4d4"
  },
  "tokenColors": [
    {
      "scope": "keyword.operator",
      "settings": { "foreground": "#d4d4d4" }
    }
  ]
}
```

**Mapping challenge:** TextMate scopes don't map 1:1 to Neovim highlight groups.
Example: `keyword.control.flow` (VSCode) vs `@keyword.return` (Neovim)

Sources:
- [VSCode Color Theme Guide](https://code.visualstudio.com/api/extension-guides/color-theme)
- [VSCode Semantic Highlight Guide](https://code.visualstudio.com/api/language-extensions/semantic-highlight-guide)

### Neovim Colorscheme Frameworks

#### Lush.nvim

**What it is:** DSL for defining Neovim themes with real-time preview

**Key features:**
- HSL color manipulation (`color:rotate(30)`)
- Export to plain Lua, VimScript, or any format
- Real-time feedback while editing
- Can be used without runtime dependency

**Current status:** Still maintained but Neovim's APIs have matured enough that plain Lua is sufficient.

Sources:
- [rktjmp/lush.nvim](https://github.com/rktjmp/lush.nvim)

#### nvim-highlite

**What it is:** Colorscheme generator that creates comprehensive themes from minimal input

**Key features:**
- Only need 6 colors to generate a full theme
- Import any existing colorscheme and add modern highlight support
- Export to formats other applications use
- Utilities for extending/merging highlight groups

**Limitation:** Doesn't generate cterm highlights (GUI only)

Sources:
- [Iron-E/nvim-highlite](https://github.com/Iron-E/nvim-highlite)

#### mini.colors

**What it is:** Colorscheme tweaker and converter

**Key features:**
- Modify any loaded colorscheme (saturation, hue, etc.)
- Infer cterm from GUI colors
- Extract palette from any colorscheme
- Interactive experimentation with `<M-a>` apply

Sources:
- [echasnovski/mini.colors](https://github.com/echasnovski/mini.colors)

---

## Part 2: Current State Analysis

### Existing Theme Infrastructure

```text
apps/common/theme/
├── library/                    # 27 theme packages
│   ├── gruvbox-dark-hard/
│   │   ├── palette.yml         # Source palette (base16 + ANSI + special)
│   │   ├── ghostty.conf        # Generated
│   │   ├── alacritty.toml      # Generated
│   │   ├── kitty.conf          # Generated
│   │   ├── tmux.conf           # Generated
│   │   ├── neovim.lua          # Just plugin reference (not generated)
│   │   └── ...
│   └── .../
├── lib/                        # Generation code
├── analysis/                   # Palette extraction experiments
└── bin/                        # CLI tools
```

### Current Palette Format (palette.yml)

```yaml
name: "Theme Name"
author: "Source"
variant: "dark"
source: "Ghostty built-in theme"

palette:
  base00: "#1d2021"  # Background
  base01: "#928374"  # Lighter BG
  ...
  base0F: "#b16286"  # Accent

ansi:
  black: "#1d2021"
  red: "#cc241d"
  ...
  bright_white: "#ebdbb2"

special:
  background: "#1d2021"
  foreground: "#ebdbb2"
  cursor: "#ebdbb2"
  selection_bg: "#665c54"
```

### Themes Currently Supported

From theme library:
- gruvbox-dark-hard, gruvbox-dark-medium
- kanagawa, nord, rose-pine, rose-pine-moon
- nightfox, oceanicnext, everforest-dark-hard
- github-dark, github-dark-dimmed
- material-design-colors
- 15+ others (broadcast, pandora, popping-and-locking, etc.)

### Gap Analysis

| Capability | Current | Desired |
|------------|---------|---------|
| Terminal themes | ✅ Full generation | ✅ Keep |
| Neovim themes | ❌ Just plugin refs | Generate full colorschemes |
| Multiple sources | ❌ Ghostty only | base16 + ghostty + neovim + custom |
| VSCode | ❌ Not supported | Generate compatible themes |
| Comparison | ❌ Manual | Side-by-side visual comparison |

---

## Part 3: Proposed Architecture

### Core Concept: Theme Variants (Flat Structure)

Instead of one "gruvbox" theme, we maintain multiple variants at top-level for easy discovery:

```bash
apps/common/theme/themes/
├── gruvbox-dark-hard-base16/     # From tinted-theming base16
│   ├── theme.yml                 # Canonical palette
│   ├── ghostty.conf
│   ├── alacritty.toml
│   ├── neovim/                   # Generated Neovim colorscheme
│   └── ...
├── gruvbox-dark-hard-ghostty/    # From Ghostty built-in
├── gruvbox-dark-hard-neovim/     # From gruvbox.nvim palette
├── gruvbox-dark-medium-base16/
├── gruvbox-dark-medium-ghostty/
└── ...
```

Naming convention: `{theme}-{variant}-{source}`
- theme: gruvbox, kanagawa, nord, etc.
- variant: dark-hard, dark-medium, light, wave, moon, etc.
- source: base16, ghostty, neovim, omarchy (custom)

Each variant generates ALL app configs, allowing direct comparison.

### Canonical Palette Format (Extended)

```yaml
# theme.yml - Extended palette format
meta:
  name: "Gruvbox Dark Hard"
  author: "Original Author"
  variant: "dark"
  source: "neovim-gruvbox"  # or "base16", "ghostty", "custom"
  version: "1.0.0"

# Base16 slots (required)
base16:
  base00: "#1d2021"  # Background
  base01: "#3c3836"  # Lighter BG
  base02: "#504945"  # Selection BG
  base03: "#665c54"  # Comments
  base04: "#928374"  # Dark FG
  base05: "#ebdbb2"  # Foreground
  base06: "#d5c4a1"  # Light FG
  base07: "#fbf1c7"  # Lightest
  base08: "#fb4934"  # Red
  base09: "#fe8019"  # Orange
  base0A: "#fabd2f"  # Yellow
  base0B: "#b8bb26"  # Green
  base0C: "#8ec07c"  # Cyan
  base0D: "#83a598"  # Blue
  base0E: "#d3869b"  # Purple
  base0F: "#d65d0e"  # Brown

# Extended palette (optional, for richer themes)
extended:
  # Grays (more granular than base16)
  bg_dim: "#141617"
  bg_alt: "#282828"
  fg_dim: "#a89984"

  # Additional accents (from Neovim colorschemes)
  spring_green: "#98bb6c"
  wave_blue: "#7fb4ca"
  sakura_pink: "#d27e99"

  # Semantic colors
  git_add: "#76946a"
  git_change: "#dca561"
  git_delete: "#c34043"

# ANSI terminal colors (derived or explicit)
ansi:
  black: "#1d2021"
  red: "#cc241d"
  green: "#98971a"
  yellow: "#d79921"
  blue: "#458588"
  magenta: "#b16286"
  cyan: "#689d6a"
  white: "#a89984"
  bright_black: "#928374"
  bright_red: "#fb4934"
  bright_green: "#b8bb26"
  bright_yellow: "#fabd2f"
  bright_blue: "#83a598"
  bright_magenta: "#d3869b"
  bright_cyan: "#8ec07c"
  bright_white: "#ebdbb2"

# Special purpose colors
special:
  background: "#1d2021"
  foreground: "#ebdbb2"
  cursor: "#ebdbb2"
  cursor_text: "#1d2021"
  selection_bg: "#665c54"
  selection_fg: "#ebdbb2"
  border: "#504945"
  panel: "#282828"
```

### Neovim Colorscheme Template

Standardized Lua structure based on kanagawa.nvim architecture:

```bash
colorschemes/{theme-name}/
├── lua/
│   └── {theme-name}/
│       ├── init.lua          # Entry point, setup function
│       ├── palette.lua       # Color definitions (from theme.yml)
│       ├── groups/
│       │   ├── editor.lua    # UI highlights
│       │   ├── syntax.lua    # Traditional syntax
│       │   ├── treesitter.lua # @captures
│       │   ├── lsp.lua       # @lsp.* and diagnostics
│       │   └── plugins/
│       │       ├── telescope.lua
│       │       ├── cmp.lua
│       │       ├── gitsigns.lua
│       │       └── ...
│       └── extras/           # Generated for other apps
│           ├── ghostty.lua
│           ├── alacritty.lua
│           └── ...
├── colors/
│   └── {theme-name}.lua      # :colorscheme entry
└── extras/                   # Pre-generated configs
    ├── ghostty/{theme}.conf
    ├── alacritty/{theme}.toml
    └── ...
```

### Semantic Color Mapping

Define consistent semantic mappings across all colorschemes:

```lua
-- semantic.lua - Standard semantic color assignments
local semantic = {
  -- Syntax semantics (palette color → semantic role)
  syntax = {
    comment = "base03",
    string = "base0B",        -- green
    number = "base09",        -- orange
    boolean = "base09",
    constant = "base09",
    identifier = "base05",
    variable = "base05",
    parameter = "base0E",     -- purple (italic)
    field = "base0C",         -- cyan
    property = "base0C",
    function_name = "base0D", -- blue
    method = "base0D",
    keyword = "base0E",       -- purple
    operator = "base05",
    type = "base0A",          -- yellow
    constructor = "base0A",
    namespace = "base0C",
    punctuation = "base04",
    tag = "base08",           -- red
    attribute = "base0A",
  },

  -- UI semantics
  ui = {
    background = "base00",
    foreground = "base05",
    cursor_line = "base01",
    selection = "base02",
    border = "base02",
    panel = "base01",
    status_bg = "base01",
    status_fg = "base04",
  },

  -- Diagnostic semantics
  diagnostic = {
    error = "base08",
    warning = "base09",
    info = "base0D",
    hint = "base0C",
    ok = "base0B",
  },

  -- Git semantics
  git = {
    add = "base0B",
    change = "base0A",
    delete = "base08",
  },
}
```

### Generation Pipeline

```text
┌─────────────────┐
│  Source Palette │  (base16.yaml, ghostty theme, neovim palette.lua)
└────────┬────────┘
         │ Extract
         ▼
┌─────────────────┐
│   theme.yml     │  (Canonical extended palette format)
└────────┬────────┘
         │ Generate
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Output Generators                        │
├─────────────┬─────────────┬─────────────┬─────────────┬─────┤
│  Terminal   │   Neovim    │   VSCode    │   Desktop   │ ... │
│  Configs    │ Colorscheme │   Theme     │   Themes    │     │
└─────────────┴─────────────┴─────────────┴─────────────┴─────┘
         │
         ▼
┌─────────────────┐
│  Theme Package  │
│  ├── ghostty    │
│  ├── alacritty  │
│  ├── neovim/    │
│  ├── vscode/    │
│  └── ...        │
└─────────────────┘
```

---

## Part 4: Implementation Plan (Gruvbox First)

**Strategy**: Complete ALL phases with gruvbox variants only. Learn, iterate, refine. Then expand to other themes.

### Phase 1: Gruvbox Palette Extraction

**Goal:** Create theme.yml files for gruvbox from all 3 sources

**Gruvbox Variants to Create:**
- `gruvbox-dark-hard-base16` (from tinted-theming)
- `gruvbox-dark-hard-ghostty` (from Ghostty built-in)
- `gruvbox-dark-hard-neovim` (from ellisonleao/gruvbox.nvim)
- `gruvbox-dark-medium-base16`
- `gruvbox-dark-medium-ghostty`
- `gruvbox-dark-medium-neovim`
- `gruvbox-dark-soft-base16`
- `gruvbox-dark-soft-ghostty`
- `gruvbox-dark-soft-neovim`
- (Light variants if desired)

**Tasks:**
1. Create `themes/` directory structure
2. Define `theme.yml` schema
3. Extract gruvbox palettes from:
   - Base16 canonical (`~/.local/share/tinted-theming/...`)
   - Ghostty themes (`/Applications/Ghostty.app/.../themes/`)
   - gruvbox.nvim palette (`~/.local/share/nvim/lazy/gruvbox.nvim/`)
4. Create comparison showing differences between sources

**Output:** 9+ gruvbox theme.yml files with documented differences

### Phase 2: Gruvbox Neovim Colorscheme Generation

**Goal:** Generate comprehensive Neovim colorscheme for gruvbox variants

**Tasks:**
1. Define semantic mapping (which base16 slot → which syntax role)
2. Create Neovim colorscheme template with ~200+ highlight groups:
   - Editor UI (~50 groups)
   - Vim syntax (~20 groups)
   - Treesitter captures (~60 groups)
   - LSP semantic tokens (~30 groups)
   - Diagnostics (~15 groups)
   - Common plugins (telescope, cmp, gitsigns, etc.)
3. Generate `gruvbox-dark-hard-base16/neovim/` colorscheme
4. Test in Neovim, compare to ellisonleao/gruvbox.nvim visually
5. Iterate until generated colorscheme matches quality

**Output:** Working Neovim colorscheme generated from theme.yml

### Phase 3: Gruvbox Terminal Generation

**Goal:** Generate all terminal configs for gruvbox variants

**Tasks:**
1. Create generators that read theme.yml → app config
2. Generate for gruvbox variants:
   - ghostty.conf
   - alacritty.toml
   - kitty.conf
   - tmux.conf
   - btop.theme
   - (other apps as needed)
3. Compare generated configs to existing library/ versions
4. Verify visual consistency across apps

**Output:** Complete terminal config set for all gruvbox variants

### Phase 4: Gruvbox VSCode Theme

**Goal:** Generate VSCode theme for gruvbox variants

**Tasks:**
1. Create TextMate scope → base16 mapping
2. Generate VSCode theme JSON for gruvbox-dark-hard-base16
3. Test in VSCode with Python, TypeScript, Lua
4. Compare to popular gruvbox VSCode extensions
5. Iterate until acceptable

**Output:** Usable VSCode theme for gruvbox

### Phase 5: Theme CLI and Variant Management

**Goal:** Create `theme` CLI to manage and switch variants

**Tasks:**
1. Create `theme list` - show all available themes
2. Create `theme apply <name>` - apply a theme to all apps
3. Create `theme compare <a> <b>` - visual comparison
4. Integration with Neovim (auto-load generated colorscheme)
5. Deprecation path from theme-sync

**Output:** Working `theme` CLI that replaces theme-sync

### Phase 6: Expansion to Other Themes

**Goal:** Apply learnings from gruvbox to remaining themes

**Tasks:**
1. Document lessons learned from gruvbox implementation
2. Create batch extraction for remaining themes
3. Generate all variants for priority themes
4. Add themes from favorites that aren't covered
5. Handle edge cases discovered

**Output:** Full theme library with all variants

---

## Part 5: Technical Decisions

### Language Choice: Python + Lua

**Python for:**
- Palette extraction from diverse sources
- Theme.yml manipulation
- Batch generation
- Testing and comparison

**Lua for:**
- Neovim colorscheme template (runtime)
- Integration with Neovim ecosystem
- Potential lush.nvim integration

### File Format: YAML for Palettes, Lua for Neovim

- YAML is human-readable and well-supported
- Lua is native to Neovim, no parsing needed
- Jinja2 templates for other app formats

### Testing Strategy

1. **Visual regression:** Generate screenshots, compare diffs
2. **Coverage testing:** Verify all highlight groups are defined
3. **Cross-platform:** Test on macOS, Linux (WSL), Arch
4. **Comparison baseline:** Use kanagawa.nvim as "gold standard" for coverage

---

## Part 6: Theme Selection

### Core Themes (must have all variants)

| Theme | Neovim Plugin | Base16 | Ghostty | Status |
|-------|---------------|--------|---------|--------|
| gruvbox | ellisonleao/gruvbox.nvim | ✅ | ✅ | Priority |
| kanagawa | rebelot/kanagawa.nvim | ✅ | ✅ | Priority |
| rose-pine | rose-pine/neovim | ✅ | ✅ | Priority |
| nord | shaunsingh/nord.nvim | ✅ | ✅ | Priority |
| tokyonight | folke/tokyonight.nvim | ✅ | ✅ | Priority |
| everforest | sainnhe/everforest | ✅ | ✅ | Priority |
| catppuccin | catppuccin/nvim | ❌ (26 colors) | ✅ | Special |

### Extended Themes (favorites.yml equivalent)

From current theme library:
- nightfox, terafox, carbonfox
- github-dark, github-dark-dimmed
- solarized-osaka
- oceanic-next
- material-design-colors (expand)
- flexoki-moon variants

### Custom/Personal Themes

- datapointchris (to be created)
- Original tmux colors (to be extracted)
- Any custom variants discovered during comparison

---

## Part 7: Success Criteria (Gruvbox First)

### Phase 1 Complete When:

- [ ] `themes/gruvbox-dark-hard-base16/theme.yml` exists
- [ ] `themes/gruvbox-dark-hard-ghostty/theme.yml` exists
- [ ] `themes/gruvbox-dark-hard-neovim/theme.yml` exists
- [ ] Comparison document shows color differences between 3 sources
- [ ] Decision made on which variants to continue (dark-hard only? all?)

### Phase 2 Complete When:

- [ ] `gruvbox-dark-hard-base16/neovim/` is installable colorscheme
- [ ] Generated colorscheme has 200+ highlight groups
- [ ] Treesitter, LSP, diagnostics fully covered
- [ ] Visual comparison to ellisonleao/gruvbox.nvim is acceptable
- [ ] Can use generated colorscheme as daily driver

### Phase 3 Complete When:

- [ ] All terminal configs generated from theme.yml
- [ ] ghostty, alacritty, kitty, tmux, btop generated for gruvbox variants
- [ ] Generated configs match existing library/ quality
- [ ] Switching works across all apps

### Phase 4 Complete When:

- [ ] VSCode theme JSON generated for gruvbox-dark-hard-base16
- [ ] Python and Lua syntax highlighting looks correct
- [ ] Theme can be loaded in VSCode manually

### Phase 5 Complete When:

- [ ] `theme list` shows all gruvbox variants
- [ ] `theme apply gruvbox-dark-hard-base16` works
- [ ] Neovim loads generated colorscheme automatically
- [ ] Documentation for using new system

### Phase 6 Complete When:

- [ ] Lessons documented from gruvbox implementation
- [ ] Process for adding new themes documented
- [ ] At least 5 additional themes fully generated
- [ ] Old library/ can be deprecated (not deleted)

---

## Part 8: Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Neovim highlight groups change | Generated themes break | Pin to Neovim version, test matrix |
| Plugin highlights vary widely | Incomplete coverage | Focus on plugins in LazyVim config |
| Color perception differs | Variants look "wrong" | Use Delta E for objective comparison |
| VSCode scope mapping imperfect | Colors don't match | Accept ~90% match, document differences |
| Maintenance burden too high | System abandoned | Automate everything, minimal manual steps |

---

## Part 9: Open Questions (To Discuss Before Each Phase)

**Before starting each phase, clarifying questions should be asked and answered.**

### Phase 1 Questions:

1. **Which gruvbox variants to start with?**
   - Just dark-hard for initial iteration?
   - All dark variants (hard, medium, soft)?
   - Include light variants?

2. **Where should `themes/` directory live?**
   - `apps/common/theme/themes/` (alongside existing library)?
   - New top-level location?

3. **What additional colors beyond base16 should theme.yml include?**
   - Just base16 + ANSI + special?
   - Extended palette with semantic names?

### Phase 2 Questions:

4. **Which Neovim plugins to support in highlight groups?**
   - Core only: telescope, cmp, gitsigns, treesitter, lsp?
   - Full LazyVim plugin set?
   - User's specific plugins?

5. **Should generated colorschemes be installable via Lazy.nvim?**
   - Local path reference?
   - Symlink into plugin directory?

### Phase 4 Questions:

6. **VSCode: Extension or just JSON files?**
   - Extension: Easier to install, requires publishing
   - JSON: Manual install, but simpler for personal use

### General Questions:

7. **Should theme variants live in dotfiles or separate repo?**
   - Dotfiles: Single source of truth
   - Separate: Cleaner separation, easier sharing

---

## Appendix: Reference Links

### Neovim Colorscheme Development

- [Build Your Own Neovim Colorscheme in Lua](https://medium.com/@ronxvier/build-your-own-neovim-colorscheme-in-lua-3b01adf019e0)
- [rktjmp/lush.nvim](https://github.com/rktjmp/lush.nvim) - Theme DSL
- [Iron-E/nvim-highlite](https://github.com/Iron-E/nvim-highlite) - Generator framework
- [echasnovski/mini.colors](https://github.com/echasnovski/mini.colors) - Converter/tweaker
- [rebelot/kanagawa.nvim](https://github.com/rebelot/kanagawa.nvim) - Reference architecture

### Cross-Editor Theming

- [tinted-theming/home](https://github.com/tinted-theming/home) - Base16 ecosystem
- [tinted-theming/tinty](https://github.com/tinted-theming/tinty) - Theme manager
- [mjswensen/themer](https://github.com/mjswensen/themer) - Multi-editor generator
- [Catppuccin Style Guide](https://github.com/catppuccin/catppuccin/blob/main/docs/style-guide.md)
- [folke/tokyonight.nvim extras](https://github.com/folke/tokyonight.nvim) - Extras generation

### VSCode Theming

- [VSCode Color Theme Guide](https://code.visualstudio.com/api/extension-guides/color-theme)
- [VSCode Semantic Highlight Guide](https://code.visualstudio.com/api/language-extensions/semantic-highlight-guide)
- [VSCode Syntax Highlight Guide](https://code.visualstudio.com/api/language-extensions/syntax-highlight-guide)

### Color Science

- [Delta E Color Difference](https://en.wikipedia.org/wiki/Color_difference)
- [OKLCH Color Space](https://oklch.com/)

---

## Part 10: Next Steps

### To Start Phase 1:

1. **Answer Phase 1 questions** (see Part 9)
2. **Create directory structure**: `apps/common/theme/themes/`
3. **Define theme.yml schema** (finalize format)
4. **Extract gruvbox-dark-hard from 3 sources**:
   - Base16: `~/.local/share/tinted-theming/tinty/repos/schemes/base16/gruvbox-dark-hard.yaml`
   - Ghostty: `/Applications/Ghostty.app/Contents/Resources/ghostty/themes/Gruvbox Dark Hard`
   - Neovim: `~/.local/share/nvim/lazy/gruvbox.nvim/lua/gruvbox/palette.lua`
5. **Create comparison document** showing differences
6. **Review and decide** on next variants

### Files to Create in Phase 1:

```text
apps/common/theme/
├── themes/                              # NEW directory
│   ├── gruvbox-dark-hard-base16/
│   │   └── theme.yml
│   ├── gruvbox-dark-hard-ghostty/
│   │   └── theme.yml
│   └── gruvbox-dark-hard-neovim/
│       └── theme.yml
└── analysis/
    └── GRUVBOX_SOURCE_COMPARISON.md     # NEW comparison doc
```

### Existing Infrastructure (UNCHANGED):

```text
apps/common/theme/
├── library/                             # KEEP - existing themes
├── lib/                                 # KEEP - existing generators
├── bin/                                 # KEEP - existing CLI
└── data/                                # KEEP - existing data
```

---

## Part 11: Final Status (Completed 2024-12-30)

### What Was Built

The unified theme system is fully operational:

1. **39 themes** with terminal configs (ghostty, tmux, btop, kitty, alacritty, hyprland, waybar, etc.)
2. **20 themes** with generated Neovim colorschemes (winners that replace original plugins)
3. **16 generators** for all supported applications
4. **Complete CLI** (`theme`) with preview, apply, like/dislike, ranking, history

### Architecture Evolution

We deviated from the original "gruvbox first" approach:

| Original Plan | What We Built |
|---------------|---------------|
| Suffix naming (`-base16/-ghostty/-neovim`) | Simple names (`gruvbox-dark-hard`) |
| Iterate on one theme | Built all themes in parallel |
| Generate Neovim for all | Only "winners" get generated Neovim |

**Key insight:** Most themes work best with original Neovim plugin + generated terminal configs. Hand-crafted Neovim plugins (kanagawa, nordic) look better than mechanical generation.

### Final Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Palette Extraction | ✅ Complete | 39 themes with theme.yml |
| Phase 2: Neovim Generation | ✅ Complete | 20 themes with generated colorschemes |
| Phase 3: Terminal Generation | ✅ Complete | All 16 generators, all themes covered |
| Phase 4: VSCode Theme | ⏭️ Skipped | Not needed - VS Code has native themes |
| Phase 5: Theme CLI | ✅ Complete | preview, apply, like, rank, log |
| Phase 6: Expansion | ✅ Complete | 39 themes total |

### Deprecation Status

| Item | Status |
|------|--------|
| `library/` directory | ✅ Removed (replaced by `themes/`) |
| `ghostty-theme` app | ✅ Removed |
| `theme-sync` app | ✅ Removed |
| tinty dependency | ✅ Removed from packages.yml, uninstalled |

### Theme Inventory (39 themes)

**With generated Neovim colorscheme (20):**
black-metal-mayhem, broadcast, everforest-dark-hard, github-dark, gruvbox-dark-hard,
gruvbox-dark-medium, material-design-colors, pandora, popping-and-locking, raycast-dark,
retro-legends, rose-pine-darker, rose-pine-moon, selenized-dark, shades-of-purple,
smyck, spacedust, spacegray-eighties, srcery, tomorrow-night-bright, treehouse

**Terminal configs only (use original Neovim plugin) (19):**
carbonfox, flexoki-moon-*, github_dark_default, github_dark_dimmed, gruvbox,
kanagawa, nightfox, nordic, OceanicNext, retrobox, rose-pine, slate,
solarized-osaka, terafox

### Key Insights

1. **Hand-crafted beats mechanical**: Original Neovim plugins use hand-tuned highlight assignments
2. **`neovim_colorscheme` field is critical**: Theme preview uses it to load correct colorscheme
3. **Winners are rare**: Most themes work best with original plugin + generated terminal configs

### Files Reference

| Location | Purpose |
|----------|---------|
| `apps/common/theme/bin/theme` | Theme CLI |
| `apps/common/theme/themes/` | All 39 themes with configs |
| `apps/common/theme/lib/generators/` | 16 app generators |
| `apps/common/theme/lib/neovim_generator.py` | Neovim colorscheme generator |
| `apps/common/theme/CLAUDE.md` | Development context |

**This plan is now archived. The theme system is complete and in daily use.**
