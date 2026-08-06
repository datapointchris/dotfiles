# Hyprland

The Arch desktop's compositor. Config lives in `configs/archlinux/.config/hypr/`
and deploys with the rest of the platform overlay — Hyprland discovers it by path
and cannot branch on a feature flag, which is why it is an overlay rather than an
entry in `install/flags.yml`.

`hyprland.conf` holds only the environment variables and one `source` line per
area. Everything else is in `conf/`: `monitors`, `workspaces`, `input`,
`appearance`, `keybindings`, `windowrules`, `autostart`. The split exists so a
change has one obvious home and a syntax error names the area it broke.
`hypridle.conf`, `hyprlock.conf` and `hyprpaper.conf` sit alongside because those
are separate daemons with their own config files, not part of the compositor's.

## Keybindings mirror the macOS AeroSpace config

The bindings are deliberately the same shape as `configs/macos/.config/aerospace/`
— `SUPER` where macOS uses `alt`, `h`/`j`/`k`/`l` to move focus, the same keys
with `SHIFT` to move the window. Two machines, one set of muscle memory. Read the
AeroSpace config alongside this one before changing either; a binding that exists
on only one desk is the failure this arrangement is avoiding.

Every binding uses `bindd` rather than `bind`. The extra field is a description,
and `rofi-keybinds` (`apps/archlinux/rofi-keybinds`) parses it to build the
cheatsheet on `SUPER+SHIFT+/`. A `bind` written without a description silently
disappears from that list, so it is `bindd` throughout even where the description
reads as obvious.

## Workspaces are named, not numbered

`workspace = name:A, persistent:true` and so on for B, D, E, M, S, X, Z — the
letter is the mnemonic and the key that reaches it, so `SUPER+D` goes to D. This
follows the AeroSpace config for the same muscle-memory reason. `persistent:true`
keeps them in waybar when empty, which is what makes the set feel fixed rather
than appearing and vanishing as windows open.

Workspace 9 is the exception and is numbered, unnamed in waybar, and bound to
`HDMI-A-1`.

## The second output is disabled by default

`conf/monitors.conf` declares a catch-all `monitor = , preferred, auto, 1` and
then `monitor = HDMI-A-1, disable`. The explicit `disable` has to come after the
catch-all or the catch-all claims it.

The HDMI run goes to the work desk's monitor. Leaving it live makes Hyprland
spread workspaces across two physical desks, so it stays off and the
`work-monitor` app enables it on demand — see [work-monitor](../apps/work-monitor.md),
which also documents why that tool keeps its own state file instead of asking
`hyprctl`.

## Theming

`configs/archlinux/.config/hypr/themes/` is the target for generated theme
output. Colour comes from a named theme via the `theme` tool rather than being
extracted from the wallpaper, so the palette is reproducible across machines and
does not shift when the background changes.

For background on Wayland compositors generally, what Hyprland owns that a
window manager does not, and the companion-application landscape, see
[Understanding Hyprland](https://docs.ichrisbirch.com/linux/understanding-hyprland/)
on the hub.
