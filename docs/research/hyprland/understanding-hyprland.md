# Understanding Hyprland: Concepts and Architecture

This document provides a comprehensive explanation of Hyprland, how it differs from desktop environments and window managers like AeroSpace, and guidance for integrating Hyprland configurations into these dotfiles.

## Table of Contents

1. [The Wayland Display Model](#the-wayland-display-model)
2. [Hyprland vs Desktop Environments](#hyprland-vs-desktop-environments)
3. [Hyprland vs AeroSpace](#hyprland-vs-aerospace)
4. [Required Companion Applications](#required-companion-applications)
5. [Configuration Structure](#configuration-structure)
6. [Popular Dotfiles Analysis](#popular-dotfiles-analysis)
7. [Theming Approaches](#theming-approaches)

## The Wayland Display Model

### X11 Architecture (Traditional)

In the X11 world, display management was split across three separate components:

- **X Server (Xorg)**: The display server that handles graphics rendering and input
- **Window Manager**: Controls window placement, decorations, and focus (e.g., i3, openbox)
- **Compositor**: Handles transparency, animations, and visual effects (e.g., picom, compton)

This separation allowed mixing and matching components, but created complexity and performance overhead.

### Wayland Architecture (Modern)

Wayland replaces this with a unified model. A **Wayland compositor** handles all three roles:

- Speaks the Wayland protocol (replacing X server)
- Manages window placement and focus (window manager)
- Handles visual effects and rendering (compositor)

**Hyprland is a Wayland compositor**. This means it is the equivalent of Xorg + i3 + picom combined into a single tightly-integrated application.

Key implications:

- You cannot run multiple window managers under Wayland
- You cannot swap out the compositor for another
- All window management, effects, and input handling are controlled by Hyprland

### The "Not a Desktop Environment" Clarification

When Hyprland documentation says it is "not a desktop environment," this means:

**What Hyprland provides:**

- Window management (tiling, floating, focus)
- Input handling (keyboard, mouse, touchpad)
- Visual effects (animations, blur, rounded corners)
- Monitor configuration
- Workspace management
- Basic session management

**What Hyprland does NOT provide:**

- Notification daemon
- Status bar / panel
- Application launcher
- Clipboard manager
- Screen locker
- Power management / idle handling
- Wallpaper manager
- File manager
- Screenshot tools
- Authentication dialogs (polkit agent)
- Sound/volume control GUI

A full desktop environment like GNOME or KDE bundles all of these together. With Hyprland, you assemble these components yourself, choosing the specific tools you prefer.

## Hyprland vs Desktop Environments

### GNOME/KDE Approach

Desktop environments provide a complete, integrated experience:

```text
GNOME Desktop Environment
├── Mutter (Compositor)
├── GNOME Shell (Panel, Launcher, Notifications)
├── Nautilus (File Manager)
├── Settings (GUI Configuration)
├── Keyring (Secrets Management)
├── GNOME Tweaks (Customization)
└── Everything "just works" together
```

**Pros:**

- Consistent visual design
- Deep integration between components
- Works out of the box
- GUI configuration for most settings

**Cons:**

- Limited customization flexibility
- Cannot swap individual components
- Heavier resource usage
- Opinionated workflow

### Hyprland Approach

You build your environment from independent components:

```text
Hyprland Setup
├── Hyprland (Compositor + Window Manager)
├── Waybar or AGS (Status Bar) [YOUR CHOICE]
├── Rofi or Wofi (Launcher) [YOUR CHOICE]
├── Dunst or Mako (Notifications) [YOUR CHOICE]
├── hyprpaper or swww (Wallpaper) [YOUR CHOICE]
├── hyprlock + hypridle (Lock Screen) [YOUR CHOICE]
├── cliphist or copyq (Clipboard) [YOUR CHOICE]
├── Yazi or Nautilus (File Manager) [YOUR CHOICE]
└── Configuration is text files
```

**Pros:**

- Complete control over every component
- Lightweight (only run what you need)
- Text-based configuration (version controllable)
- Highly customizable appearance and behavior

**Cons:**

- Requires initial configuration effort
- Must learn each component separately
- No central GUI for settings
- Integration is your responsibility

## Hyprland vs AeroSpace

This comparison is essential for understanding what to expect coming from macOS.

### AeroSpace (macOS)

AeroSpace is a **window manager only** running on top of the macOS display system:

```text
macOS Display Stack
├── WindowServer (Apple's display server)
├── System Compositor (Apple-controlled)
├── Mission Control / Spaces (Apple's workspace system)
└── AeroSpace (sits on top, arranges windows)
```

**What AeroSpace does:**

- Arranges windows in tiling layouts
- Provides keyboard shortcuts for window navigation
- Creates virtual workspaces (replacing macOS Spaces)
- Window focus management

**What AeroSpace does NOT do:**

- Render windows (macOS handles this)
- Handle input events at system level
- Control animations or visual effects
- Manage the display or compositing

AeroSpace philosophy: Minimal, practical, no "ricing." Gaps are supported, but fancy borders, blur, and animations are not a focus.

### Hyprland (Linux)

Hyprland is the **entire display system**:

```text
Hyprland Display Stack
├── Hyprland (IS the display server)
├── Hyprland (IS the compositor)
├── Hyprland (IS the window manager)
└── Everything else is external applications
```

**What Hyprland does:**

- Speaks Wayland protocol (applications render to it)
- Composites all windows (with effects: blur, shadows)
- Manages window tiling and floating
- Handles all input (keyboard, mouse, touchpad gestures)
- Controls animations for everything
- Manages monitors and workspaces
- Provides IPC for external tools

**Key difference:** AeroSpace operates within constraints set by macOS. Hyprland has no constraints—it IS the constraint. Everything visual happens through Hyprland.

### Conceptual Mapping

| Feature | AeroSpace (macOS) | Hyprland (Linux) |
|---------|-------------------|------------------|
| Window tiling | Yes | Yes |
| Workspaces | Yes (virtual) | Yes (native) |
| Focus follows mouse | No (macOS limitation) | Yes (configurable) |
| Window animations | No (macOS handles) | Yes (fully customizable) |
| Window borders | Minimal (gaps only) | Full control (color, size, radius) |
| Blur effects | No | Yes |
| Rounded corners | No | Yes |
| Status bar | External (e.g., SketchyBar) | External (Waybar, etc.) |
| App launcher | External (Alfred, etc.) | External (Rofi, etc.) |
| Configuration | TOML file | Text config files |

### Your Current AeroSpace Config Patterns

Looking at your aerospace.toml, you use:

- Direct workspace access with `Alt + letter` (A, B, D, E, M, S, X, Z)
- Alt as primary modifier
- vim-style movement (h, j, k, l)
- Resize mode (`Alt + r` then h/j/k/l)
- JankyBorders for window focus indication
- Ghostty as terminal

These patterns translate well to Hyprland:

- Direct workspace access with `Super + letter` (same pattern, different modifier)
- Any modifier can be used (SUPER is standard on Linux)
- vim-style movement is widely used
- Hyprland supports **submaps** for resize mode
- Hyprland has native borders (no separate tool needed)
- Ghostty works on Linux with Wayland support

## Required Companion Applications

### Critical (Your Desktop Won't Work Without These)

| Component | Purpose | Recommended Options |
|-----------|---------|---------------------|
| **Notification Daemon** | Display notifications; some apps freeze without one | dunst, mako, swaync |
| **Polkit Agent** | Password prompts for privilege escalation | hyprpolkitagent, polkit-kde-agent |
| **Pipewire** | Screen sharing, audio | pipewire, wireplumber |
| **XDG Desktop Portal** | File pickers, screen sharing | xdg-desktop-portal-hyprland |
| **Qt Wayland Support** | Qt apps render correctly | qt5-wayland, qt6-wayland |

### Essential for Usability

| Component | Purpose | Recommended Options |
|-----------|---------|---------------------|
| **Status Bar** | System info, workspaces | Waybar (beginner-friendly), AGS (programmable) |
| **App Launcher** | Start applications | Rofi (powerful), Wofi (simple), fuzzel (fast) |
| **Clipboard Manager** | Clipboard history | cliphist (simple), clipvault (advanced) |
| **Screen Locker** | Lock screen | hyprlock (native) |
| **Idle Manager** | Lock/sleep on inactivity | hypridle (native) |
| **Wallpaper** | Background image | hyprpaper (native), swww (animated) |

### Recommended for Daily Use

| Component | Purpose | Recommended Options |
|-----------|---------|---------------------|
| **Screenshot Tool** | Screen capture | grim + slurp (selection), grimblast (convenient wrapper) |
| **File Manager** | Browse files | Yazi (TUI, already in your setup), Nautilus (GUI) |
| **Terminal** | You know this | Ghostty, Kitty, Alacritty |
| **Logout Menu** | Shutdown/restart menu | wlogout |
| **Brightness Control** | Screen brightness | brightnessctl |
| **Audio Control** | Volume, output | pavucontrol, wpctl |

## Configuration Structure

### File Locations

Hyprland config lives in `~/.config/hypr/`:

```text
~/.config/hypr/
├── hyprland.conf        # Main config (sources others)
├── hyprlock.conf        # Lock screen config
├── hypridle.conf        # Idle timeout config
├── hyprpaper.conf       # Wallpaper config
└── conf/                # Optional: split configs
    ├── monitors.conf
    ├── keybindings.conf
    ├── autostart.conf
    ├── animations.conf
    ├── decoration.conf
    ├── windowrules.conf
    └── custom.conf
```

### Main Config Sections

A typical hyprland.conf includes:

```ini
# Monitor configuration
monitor = name, resolution@refresh, position, scale

# Input configuration
input {
    kb_layout = us
    follow_mouse = 1
    touchpad { natural_scroll = no }
}

# Visual appearance
general {
    gaps_in = 5
    gaps_out = 10
    border_size = 2
    col.active_border = rgba(33ccffee)
}

decoration {
    rounding = 10
    blur { enabled = yes }
}

animations {
    enabled = yes
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    animation = windows, 1, 7, myBezier
}

# Keybindings
bind = $mainMod, Return, exec, ghostty
bind = $mainMod, Q, killactive
bind = $mainMod, 1, workspace, 1

# Window rules
windowrule = float, class:^(pavucontrol)$
windowrule = workspace 1, class:^(firefox)$

# Autostart
exec-once = waybar
exec-once = dunst
```

### Sourcing Pattern

Popular dotfiles split configuration into multiple files:

```ini
# hyprland.conf
source = ~/.config/hypr/conf/monitors.conf
source = ~/.config/hypr/conf/keybindings.conf
source = ~/.config/hypr/conf/autostart.conf
source = ~/.config/hypr/conf/windowrules.conf
source = ~/.config/hypr/conf/custom.conf  # User overrides
```

This pattern:

- Keeps individual files focused
- Makes it easy to swap keybinding layouts
- Allows platform-specific monitors.conf
- Supports a "custom.conf" for personal overrides

## Popular Dotfiles Analysis

### ML4W Dotfiles

**Philosophy:** Complete, user-friendly Hyprland experience with GUI settings app.

**Structure:**

```text
.config/hypr/
├── hyprland.conf           # Sources everything
├── colors.conf             # Theme colors
├── conf/
│   ├── monitor.conf        # Display setup
│   ├── keyboard.conf       # Input config
│   ├── environment.conf    # Environment variables
│   ├── autostart.conf      # Startup apps
│   ├── keybinding.conf     # Sources default.conf
│   ├── keybindings/
│   │   ├── default.conf    # QWERTY bindings
│   │   └── fr.conf         # French layout
│   ├── animation.conf
│   ├── decoration.conf
│   ├── window.conf
│   ├── windowrule.conf
│   ├── monitors/           # Preset monitor configs
│   │   ├── 1920x1080.conf
│   │   ├── 2560x1440.conf
│   │   └── ...
│   └── custom.conf         # User customization
```

**Key Features:**

- ML4W Settings App (Flatpak) for GUI configuration
- Material Design color theming (pywal-based)
- Multiple keybinding presets
- Pre-configured monitor profiles
- Waybar with custom widgets
- Rofi with styled themes

**Pros:** Most complete, easiest to get started
**Cons:** Heavy dependencies, lots of custom scripts

### Coffebar Dotfiles

**Philosophy:** Minimal, practical, developer-focused.

**Structure:**

```bash
.config/hyprland/
├── hyprland.conf           # Everything in one file
└── scripts/
    └── (helper scripts)
```

**Key Features:**

- Single-file configuration
- Minimal animations (disabled by default)
- No blur or fancy effects
- Developer-focused window rules (JetBrains, Firefox, Telegram)
- Per-window keyboard layout
- Alacritty terminal

**Pros:** Simple, fast, no dependencies
**Cons:** Less "pretty," requires more manual setup

### Omarchy (DHH's Dotfiles)

**Philosophy:** Opinionated defaults, easy customization.

**Structure:**

```text
~/.config/hypr/hyprland.conf (sources everything)
~/.local/share/omarchy/default/hypr/  # Default configs (don't edit)
    ├── autostart.conf
    ├── bindings/
    │   ├── tiling-v2.conf
    │   ├── utilities.conf
    │   ├── media.conf
    │   └── clipboard.conf
    ├── looknfeel.conf
    └── input.conf
~/.config/hypr/  # User overrides (edit these)
    ├── monitors.conf
    ├── input.conf
    ├── bindings.conf
    └── autostart.conf
```

**Key Features:**

- Split between "defaults" and "user overrides"
- Keybindings use `bindd` for self-documenting shortcuts
- Modular binding files
- Kitty terminal
- Extensive group/tabbing support

**Pros:** Clean separation of concerns, well-documented bindings
**Cons:** Requires understanding the two-layer system

## Theming Approaches

### Wallpaper-Based Theming (Pywal/Matugen)

Most popular Hyprland rices use **wallpaper-driven theming**:

1. Set a wallpaper
2. Tool extracts dominant colors (pywal, matugen)
3. Colors applied to: Waybar, Hyprland borders, terminal, Rofi, etc.
4. Everything matches your wallpaper

**ML4W uses this approach** with Material Design color extraction.

### Unified Theme System (Your Current Approach)

Your dotfiles use a custom **theme** tool for unified theming. This approach:

1. Choose a theme (e.g., gruvbox-dark-hard, kanagawa, rose-pine)
2. `theme apply <name>` generates configs for: Ghostty, tmux, btop, Neovim
3. Consistent colors regardless of wallpaper
4. Themes defined in `apps/common/theme/themes/` with generators for each app

**For Hyprland integration:**

- Theme system already has generators for Hyprland, Waybar, Walker, etc.
- Each theme can generate CSS/conf for Hyprland components
- This approach is more "functional" vs "aesthetic-first"

### Recommendation

For your use case (development-focused, not rice-focused):

1. Start with a minimal config without heavy theming
2. Use your existing theme system for colors
3. Add visual polish incrementally as desired
4. Keep wallpaper separate from color scheme

## Next Steps

See the integration plan in `.planning/hyprland-integration.md` for specific implementation steps and decisions to make.

## Sources

- [Hyprland Wiki - Must-Have Utilities](https://wiki.hypr.land/Useful-Utilities/Must-have/)
- [Hyprland Wiki - Status Bars](https://wiki.hypr.land/Useful-Utilities/Status-Bars/)
- [Hyprland Wiki - App Launchers](https://wiki.hypr.land/Useful-Utilities/App-Launchers/)
- [Hyprland Wiki - Clipboard Managers](https://wiki.hypr.land/Useful-Utilities/Clipboard-Managers/)
- [Hyprland Wiki - Configuration](https://wiki.hypr.land/Configuring/Configuring-Hyprland/)
- [ML4W Dotfiles](https://github.com/mylinuxforwork/dotfiles)
- [Coffebar Dotfiles](https://github.com/coffebar/dotfiles)
- [Omarchy](https://github.com/basecamp/omarchy)
- [AeroSpace](https://github.com/nikitabobko/AeroSpace)
