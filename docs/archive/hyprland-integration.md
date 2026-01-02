# Hyprland Integration Plan

This document outlines the plan to integrate Hyprland configurations into the dotfiles repository for Arch Linux, without affecting macOS or WSL configurations.

## Status: ✅ COMPLETE

All phases have been implemented and tested. The Hyprland configuration is ready for use on Arch Linux.

## Final State

### Arch Platform Structure

```text
platforms/arch/
├── .gitconfig
├── .config/
│   ├── hypr/
│   │   ├── hyprland.conf       # Main config, sources conf/*.conf
│   │   ├── hyprlock.conf       # Lock screen
│   │   ├── hypridle.conf       # Idle timeouts
│   │   ├── conf/
│   │   │   ├── monitors.conf
│   │   │   ├── input.conf
│   │   │   ├── keybindings.conf
│   │   │   ├── autostart.conf
│   │   │   ├── appearance.conf
│   │   │   └── windowrules.conf
│   │   └── themes/             # Theme applied here by `theme apply`
│   ├── waybar/
│   │   ├── config.jsonc
│   │   ├── style.css           # Imports themes/current.css
│   │   └── themes/
│   ├── rofi/
│   │   ├── config.rasi         # Imports themes/current.rasi
│   │   └── themes/
│   ├── dunst/
│   │   └── dunstrc             # Colors via drop-in dunstrc.d/99-theme.conf
│   └── zsh/
│       └── .zprofile
└── .local/
    └── shell/
        ├── arch-aliases.sh
        └── arch-functions.sh
```

### How Platform Overlays Work

The symlinks manager uses a layered approach:

1. **Common base** (`platforms/common/`): Linked first for all platforms
2. **Platform overlay** (`platforms/arch/`): Linked second, can override common

Files in `platforms/arch/.config/hypr/` will be symlinked to `~/.config/hypr/` only on Arch systems.

### Existing macOS Configuration

Your AeroSpace config uses:

- Direct workspace access with `Alt + letter`
- Named workspaces: A, B, D, E, M, S, X, Z
- Alt as primary modifier
- vim-style navigation (h, j, k, l)
- Resize mode (`Alt + r` then h/j/k/l)
- Layout toggles (`Alt + '` and `Alt + \`)
- JankyBorders for focus indication
- Ghostty terminal integration

### Theming System

The unified `theme` CLI generates configs for all Hyprland desktop apps:

- **Hyprland**: `~/.config/hypr/themes/current.conf`
- **Waybar**: `~/.config/waybar/themes/current.css`
- **Rofi**: `~/.config/rofi/themes/current.rasi`
- **Dunst**: `~/.config/dunst/dunstrc.d/99-theme.conf` (drop-in directory)
- **Hyprlock**: `~/.config/hypr/themes/hyprlock.conf`

Run `theme apply <name>` to apply a theme across all apps.

## Implementation Phases

### Phase 1: Core Hyprland Configuration ✅

- Created modular config structure with `hyprland.conf` sourcing `conf/*.conf`
- Configured monitors, input, keybindings, autostart, appearance, windowrules
- Set up hyprlock and hypridle for screen locking

### Phase 2: Companion Applications ✅

All packages added to `management/packages.yml` with pacman entries:
waybar, rofi-wayland, dunst, wl-clipboard, cliphist, grim, slurp,
brightnessctl, playerctl, polkit-kde-agent, xdg-desktop-portal-hyprland,
hyprpaper, hyprlock, hypridle, qt5-wayland, qt6-wayland, pipewire,
wireplumber, pipewire-pulse, firefox, kitty, ghostty

### Phase 3: Application Configurations ✅

- Waybar: workspaces (A,B,D,E,M,S,X,Z), clock, cpu, memory, network, audio
- Rofi: drun/run/window modes with theme import
- Dunst: notification styling with drop-in theme support
- Hyprlock: time/date display, password input
- Hypridle: dim at 8min, lock at 10min, dpms off at 11min

### Phase 4: Theming Integration ✅

Integrated with unified `theme` system (replaced tinty):
- Added generators: `rofi.sh`, `dunst.sh` (in addition to existing hyprland, waybar, hyprlock)
- Dunst uses drop-in directory (`dunstrc.d/99-theme.conf`) instead of sed replacement
- All 39 themes regenerated with `rofi.rasi` and `dunst.conf` files

### Phase 5: Terminal Integration ✅

- Ghostty as primary terminal (TERMINAL=ghostty in hyprland.conf)
- Kitty available as fallback
- Both in packages.yml

### Phase 6: Browser ✅

- Firefox in packages.yml (Wayland native)

## Decisions Made

All key decisions have been finalized through discussion.

### Applications

| Component | Decision |
|-----------|----------|
| Status bar | Waybar |
| Launcher | Rofi |
| Terminal | Ghostty (primary), Kitty (available) |
| Notifications | Dunst |
| Clipboard | cliphist |
| Browser | Firefox |

### Visual Settings

| Setting | Decision |
|---------|----------|
| Animations | Full (will test and adjust) |
| Visual effects | Full (blur, shadows, rounded corners - will test) |

### Hardware

| Spec | Value |
|------|-------|
| Monitor | Dell U4323QE 3840x2160@60Hz |
| GPU | No NVIDIA (simpler config) |
| Form factor | Desktop |
| Scaling | 1.0 (possibly 1.25 if text too small) |

### Keybinding Philosophy

The keybinding scheme was designed with these constraints:
- 42-key Corne split keyboard with numbers on layer 2
- Desire for consistency between macOS and Linux
- vim-style navigation (h/j/k/l) preferred
- Semantic workspaces (project-based, not app-based)
- Large monitor = terminal + browser on same workspace

**Solution:** Letter-based direct workspace access on both platforms
- macOS: `Alt + letter`
- Linux: `Super + letter`
- Same pattern, platform-appropriate modifier

### Finalized Keybinding Table

| Action | macOS (AeroSpace) | Linux (Hyprland) |
|--------|-------------------|------------------|
| **Navigation** |
| Focus left/down/up/right | `Alt+h/j/k/l` | `Super+h/j/k/l` |
| Move window | `Alt+Shift+h/j/k/l` | `Super+Shift+h/j/k/l` |
| **Workspaces (A, B, D, E, M, S, X, Z)** |
| Go to workspace | `Alt+letter` | `Super+letter` |
| Move to workspace | `Alt+Shift+letter` | `Super+Shift+letter` |
| Back-and-forth | `Alt+Tab` | `Super+Tab` |
| **Windows** |
| Close window | `Alt+q` | `Super+q` |
| Toggle float | `Alt+f` | `Super+f` |
| Fullscreen | `Alt+Shift+f` | `Super+Shift+f` |
| **Apps** |
| Terminal | `Alt+Return` | `Super+Return` |
| Launcher | (Alfred) | `Super+Space` (Rofi) |
| **Modes** |
| Resize mode | `Alt+r` → h/j/k/l | `Super+r` → h/j/k/l |
| **Special** |
| Scratchpad | N/A | `Super+\` |
| Reload config | `Alt+Shift+r` | `Super+Shift+r` |

**Note on move-to-workspace M:** On macOS, `Alt+Shift+m` is used for menu, so move-to-M uses `Ctrl+Alt+m`. On Hyprland, `Super+Shift+m` works normally.

## Patterns to Adopt from Reference Dotfiles

### From ML4W

- Modular config structure with sourcing
- Keybinding organization by category
- Script-based launchers for flexibility
- Wallpaper restore on startup

### From Coffebar

- Minimal, focused approach
- Development-centric window rules
- Per-window keyboard layout (if needed)
- Submap for resize mode
- Submap for logout/exit menu

### From Omarchy

- `bindd` format for self-documenting keybindings
- Media key bindings organization
- Window grouping support

**Note:** We're NOT adopting Omarchy's "defaults vs user overrides" two-layer system. All config files are directly editable - no hand-holding abstraction. This keeps the setup standard and easier to understand while learning Hyprland.

## Reference Material

- Hyprland Wiki: https://wiki.hypr.land/
- Dunst drop-in docs: https://man.archlinux.org/man/dunst.1.en

## Completion Notes

**Completed:** 2024-12-30

All phases implemented. Ready to deploy on Arch machine with:

```bash
task symlinks:link  # Deploy configs
theme apply kanagawa  # Apply theme
```

Future improvements (not blocking):
- Add wlogout config if needed
- Test and tune animations on actual hardware
- Add hyprpaper wallpaper config if desired
