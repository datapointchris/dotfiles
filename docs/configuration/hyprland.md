# Hyprland

The Arch desktop's compositor. Config lives in `configs/display/wayland/.config/hypr/`
and deploys with the rest of that coordinate variant — Hyprland discovers it by path
and cannot branch on a feature flag, which is why it is a variant rather than an
entry in `install/flags.yml`.

## The config is Lua, because Hyprland 0.57 removes hyprlang

Hyprland 0.56 looks for `hyprland.lua` first. Without one it falls back to
`hyprland.conf` and warns at startup: "You are using the .conf config format,
support for which will be removed in Hyprland 0.57."

`hyprland.lua` holds the environment variables and one `require` per area.
Everything else is a module under `conf/`, one per area. The split exists so a
change has one obvious home and an error names the area it broke.

`hypridle.conf`, `hyprlock.conf` and `hyprpaper.conf` sit alongside and stay
hyprlang. Those are separate daemons with their own parsers, and none of them moved.

The package ships type stubs for the `hl` API at `/usr/share/hypr/stubs/`.
`.luarc.json` points lua-language-server at them, so an editor completes and
type-checks every `hl.config` key and dispatcher.

Check a change against the installed build before reloading:

```bash
Hyprland --verify-config -c ~/.config/hypr/hyprland.lua
```

It runs the whole config and exits non-zero, naming the file and line of each
unknown field, bad dispatcher argument or invalid color.

## hyprctl speaks Lua under this config

Anything that drives Hyprland from outside the config changes with it:

- `hyprctl keyword` is refused: "keyword can't work with non-legacy parsers. Use
  eval." A runtime change is `hyprctl eval '<lua>'`, such as
  `hyprctl eval 'hl.config({ decoration = { dim_inactive = true } })'`.
- `hyprctl dispatch <x>` evaluates `hl.dispatch(<x>)`, so its argument is a Lua
  dispatcher: `hyprctl dispatch 'hl.dsp.dpms({ action = "off" })'`. The hyprlang
  form `hyprctl dispatch dpms off` is a Lua syntax error.
- `hyprctl` exits 0 for any reply it receives. A script that has to know whether a
  call worked compares the reply to `ok`, as `work-monitor` does.

`screen-off`, `work-monitor` and `hypridle.conf` use the Lua forms.

## Keybindings mirror the macOS AeroSpace config

The bindings are deliberately the same shape as `configs/display/aqua/.config/aerospace/`
— `SUPER` where macOS uses `alt`, `h`/`j`/`k`/`l` to move focus, the same keys
with `SHIFT` to move the window. Two machines, one set of muscle memory. Read the
AeroSpace config alongside this one before changing either; a binding that exists
on only one desk is the failure this arrangement is avoiding.

Every binding goes through the `bind` helper in `conf/keybindings.lua`, which takes
a description as a required argument. `rofi-keybinds`
(`apps/display/wayland/rofi-keybinds`) builds the cheatsheet on `SUPER+SHIFT+/`
from `hyprctl binds`, and lists only binds that carry a description. Submap binds
appear prefixed with their submap, as `[resize] H → Shrink width`.

## Workspaces are named, not numbered

Workspaces are persistent and named by letter — the letter is the mnemonic and the
key that reaches it, so `SUPER+D` goes to D. This follows
the AeroSpace config for the same muscle-memory reason. `persistent = true` keeps
them in waybar when empty, which is what makes the set feel fixed rather than
appearing and vanishing as windows open.

Workspace 9 is the exception and is numbered, unnamed in waybar, and bound to
`HDMI-A-1`.

## The second output is disabled by default

`conf/monitors.lua` declares a catch-all rule for `output = ''` and then disables
`HDMI-A-1`. The explicit disable comes after the catch-all, so the catch-all never
claims it.

The HDMI run goes to a second desk's monitor. Leaving it live makes Hyprland
spread workspaces across two physical desks, so it stays off and the
`work-monitor` app enables it on demand — see [work-monitor](../apps/work-monitor.md),
which also documents why that tool keeps its own state file instead of asking
`hyprctl`.

## Theming

`~/.config/hypr/themes/` is the target for generated theme output, written by the
`theme` tool onto the deployed machine rather than into this repo. `hyprland.lua`
requires `themes/current.lua` after `conf/appearance.lua`, so the theme's border
colors win. `current.lua` is a stable pointer the tool repoints at whichever theme
was last applied.

Color comes from a named theme rather than being extracted from the wallpaper, so
the palette is reproducible across machines and does not shift when the background
changes.

For background on Wayland compositors generally, what Hyprland owns that a
window manager does not, and the companion-application landscape, see
[Understanding Hyprland](https://docs.ichrisbirch.com/linux/understanding-hyprland/)
on the hub.
