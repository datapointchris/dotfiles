# Hyprland Keeps the Config Format It Started With

## Problem

Hyprland 0.56 warns at startup: "You are using the .conf config format, support for which
will be removed in Hyprland 0.57." Its log says `[cfg] Lua config not found, using legacy
config at ~/.config/hypr/hyprland.conf`. Deploying a `hyprland.lua` and running
`hyprctl reload` changes nothing, because the session keeps parsing `hyprland.conf`.

Once a session is on Lua, every script that drove it through `hyprctl` breaks:

- `hyprctl keyword ...` replies `keyword can't work with non-legacy parsers. Use eval.`
- `hyprctl dispatch dpms off` replies
  `error: [string "return hl.dispatch(dpms off)"]:1: ')' expected near 'off'`
- Both exit 0, so a script running under `set -e` carries on as if they worked.

## Root Cause

Hyprland resolves its config path once, at startup, and caches it. The parser is chosen
from that path's extension. A plain reload re-reads the cached file with the parser it
already has.

Under Lua, `hyprctl dispatch <x>` is shorthand for `hl.dispatch(<x>)`, so its argument must
be a Lua expression. `keyword` has no Lua implementation at all.

## Solution

Switch a running session with `hyprctl reload full-reset`. It drops the config manager,
re-resolves the path, finds `hyprland.lua` first, and builds the Lua manager without
logging out. `hyprland.start` does not fire again, so autostart programs are not relaunched.

Convert the callers:

- `hyprctl keyword decoration:dim_inactive true` →
  `hyprctl eval 'hl.config({ decoration = { dim_inactive = true } })'`
- `hyprctl dispatch dpms off` → `hyprctl dispatch 'hl.dsp.dpms({ action = "off" })'`
- `hyprctl keyword monitor "HDMI-A-1, disable"` →
  `hyprctl eval "hl.monitor({ output = 'HDMI-A-1', disabled = true })"`

A daemon that read the old commands at startup, such as hypridle, keeps them until it is
restarted.

## Key Learnings

- Remove `hyprland.conf` only after the session is on Lua. A legacy session whose config
  disappears writes itself a default config on its next reload, through the dangling
  symlink and into the repo checkout.
- `Hyprland --verify-config -c ~/.config/hypr/hyprland.lua` checks a config against the
  installed build without starting a compositor. It names the file and line of each error.
- `hyprctl eval` is refused under the legacy parser, so a reply of `ok` from it proves the
  session is on Lua.
- Re-enabling an output needs `disabled = false` explicitly: `hl.monitor` starts from the
  rule already declared for that output.
