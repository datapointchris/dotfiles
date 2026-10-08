-- Monitor configuration
-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- `hyprctl monitors` names the outputs.

-- Auto-detect resolution (handles full 3840x2160 or half-width 1920x2160 PBP mode)
hl.monitor({ output = '', mode = 'preferred', position = 'auto', scale = 1 })

-- HDMI run to a second desk's secondary monitor. Disabled so the catch-all above
-- never picks it up — a live second output makes Hyprland spread workspaces across
-- both displays. `work-monitor` enables it on demand.
hl.monitor({ output = 'HDMI-A-1', disabled = true })
