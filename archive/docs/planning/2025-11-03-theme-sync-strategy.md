# Theme Synchronization Strategy

**Date**: 2025-11-03
**Status**: Recommended Approach

---

## Your Current Setup

### Neovim Colorschemes (17 curated favorites)

From `common/.config/nvim/lua/plugins/colorscheme-manager.lua`:

```lua
good_colorschemes = {
  'terafox',
  'solarized-osaka',
  'slate',
  'rose-pine-main',
  'retrobox',
  'carbonfox',
  'OceanicNext',
  'nordic',
  'nightfox',
  'kanagawa',
  'gruvbox',
  'github_dark_default',
  'github_dark_dimmed',
  'flexoki-moon-toddler',
  'flexoki-moon-red',
  'flexoki-moon-purple',
  'flexoki-moon-green',
  'flexoki-moon-black',
}
```

### Ghostty Theme

Currently using: `Smyck`

### Your Custom Colorscheme Manager

Your neovim setup has an impressive per-project colorscheme persistence system that:

- Saves colorscheme choice per git repository
- Auto-loads the saved theme when entering a project
- Falls back to random selection from "good_colorschemes"
- Integrates with Telescope for easy theme switching

---

## Research: Tinty Capabilities

### What Tinty Does Well

1. **Supports 250+ themes** from Base16/Base24 ecosystems
2. **Custom scheme generation** from images
3. **Highly extensible** - can theme any application via templates
4. **Hook system** for applying themes with custom shell commands
5. **Cross-platform** Rust binary

### Tinty's Limitations

1. **Locked to Base16/Base24 color systems**
   - 16-color or 24-color palettes only
   - Cannot handle arbitrary color schemes outside this spec

2. **Requires theme templates**
   - Each application needs a Base16 builder template repository
   - Custom themes must follow Base16/Base24 format

3. **Your colorschemes compatibility**:
   - ✅ **Base16-compatible**: rose-pine, gruvbox, kanagawa, nightfox, github, solarized-osaka, nordic
   - ❓ **Unclear**: terafox, carbonfox, OceanicNext, retrobox
   - ❌ **Not Base16**: flexoki-moon variants (custom modifications), slate

---

## Recommended Two-Phase Approach

### Phase 1: Quick Wins with Tinty (Weeks 3-4)

**Use tinty for immediate theme synchronization** across applications.

**Benefits**:

- Get theme sync working quickly
- 7-10 of your favorite themes will work immediately
- Learn the problem space before building custom solution
- Tinty handles the hard part (template generation) for you

**Setup**:

```bash
# Install tinty
brew install tinty

# Configure for your apps
# Create config.toml with items for:
# - ghostty
# - tmux
# - bat
# - fzf
# - eza/ls_colors

# Use the Base16-compatible themes from your list:
tinty apply base16-rose-pine
tinty apply base16-gruvbox-dark-hard
tinty apply base16-kanagawa
tinty apply base16-nightfox
```

**Limitations to accept**:

- Won't work for all 17 of your neovim themes
- Flexoki-moon variants won't be available (custom colors)
- Might need to map some theme names

### Phase 2: Custom Rust Learning Project (Future)

**Build `theme-sync` - a dotfiles-specific theme manager**

**Why this is perfect for learning Rust**:

1. **Clear, scoped problem**: Read neovim theme, apply to other apps
2. **File I/O practice**: Read/write config files
3. **String manipulation**: Parse and transform color values
4. **CLI building**: Use `clap` crate for command-line interface
5. **Error handling**: Rust's Result/Option types
6. **Project structure**: Multi-file Rust project organization

**What it would do differently than tinty**:

- Read your **exact** neovim `good_colorschemes` list as source of truth
- No Base16/Base24 constraints - work with actual theme colors
- Direct color extraction from neovim theme plugins
- Simpler config - no templates, just direct file generation
- Integrated with your existing colorscheme-manager.lua

**Feature ideas**:

```bash
# Sync current neovim theme to all apps
theme-sync

# List available themes (from neovim config)
theme-sync list

# Set specific theme everywhere
theme-sync set rose-pine-main

# Show what colors would be applied
theme-sync preview gruvbox

# Generate config for specific app
theme-sync generate ghostty --theme kanagawa
```

**Implementation sketch**:

1. Parse neovim colorscheme files (Lua or Vimscript)
2. Extract color definitions (hex values)
3. Generate configs for each target application:
   - `~/.config/ghostty/themes/<theme>.conf`
   - `~/.config/tmux/themes/<theme>.conf`
   - `~/.config/bat/themes/<theme>.tmTheme`
   - `~/.config/fzf/themes/<theme>.zsh`
4. Symlink current theme configs
5. Optional: Reload applications

**Learning resources**:

- [The Rust Book](https://doc.rust-lang.org/book/)
- [Command Line Apps in Rust](https://rust-cli.github.io/book/)
- [Clap Crate](https://docs.rs/clap/) - CLI argument parsing
- [Serde](https://serde.rs/) - Serialization for config files
- [Colored](https://docs.rs/colored/) - Terminal colors

**Complexity estimate**:

- **Simple version** (hardcoded color mappings): 2-3 days
- **Full version** (dynamic color extraction): 1-2 weeks
- **Great learning project**: Covers most Rust basics

---

## Recommendation

### For MASTER_PLAN Phase 4 (Week 3)

**Use tinty** to get theme sync working for the Base16-compatible subset of your themes.

**Pros**:

- Immediate results
- Proven, maintained tool
- Good enough for 60-70% of your themes
- Can still use tinty after building custom tool

**Cons**:

- Won't support all 17 of your neovim themes
- Locked into Base16 paradigm

### For Future Enhancement (Post-Phase 7)

**Build custom `theme-sync` Rust project** as a learning exercise and for full control.

**Pros**:

- Excellent Rust learning project
- Complete control over your exact themes
- No Base16 constraints
- Tailored to your dotfiles workflow
- Integration with your existing neovim colorscheme manager

**Cons**:

- Development time investment
- Need to maintain yourself
- More initial complexity than using tinty

---

## Decision Matrix

| Criterion | Tinty | Custom Rust Tool |
|-----------|-------|------------------|
| **Time to working** | 1-2 days | 1-2 weeks |
| **Learning opportunity** | Low | High (Rust) |
| **Theme compatibility** | ~60% (Base16 only) | 100% (all themes) |
| **Maintenance** | Community | You |
| **Flexibility** | Template-based | Full control |
| **Integration with nvim** | Separate | Native |
| **Complexity** | Medium (config) | Low (simpler) |

---

## My Specific Recommendation

1. **Week 3 (Phase 4)**: Install tinty, configure for ghostty/tmux/bat/fzf
   - Get 7-10 themes working (rose-pine, gruvbox, kanagawa, nightfox, github, nordic, solarized)
   - Learn what theme sync feels like
   - Identify what you want in a custom tool

2. **Week 6+**: Start `theme-sync` Rust project
   - Use it as your Rust learning vehicle
   - Start with hardcoded mappings (easier)
   - Gradually add dynamic color extraction
   - Can coexist with tinty

3. **Long-term**: Use whichever tool fits the need
   - Tinty: For Base16 themes and quick experiments
   - `theme-sync`: For your full curated collection

---

## Next Steps if You Choose This Path

1. **Review this recommendation** - does it align with your goals?
2. **Decide on tinty for Phase 4** - yes/no?
3. **Plan Rust project timing** - when to start learning?
4. **Update MASTER_PLAN** with this two-phase approach

---

## Alternative: Skip Tinty Entirely

If you want to jump straight to the Rust project:

**Pros**:

- Only learn one system
- Full control from day 1
- Perfect learning project

**Cons**:

- No theme sync for 1-2 weeks during development
- Might build something tinty already does well
- Harder to validate if you've never used theme sync

**My take**: Tinty gives you immediate gratification and a reference implementation. Your Rust tool can then improve on it with your specific needs.

---

*Document Status: Ready for decision*
