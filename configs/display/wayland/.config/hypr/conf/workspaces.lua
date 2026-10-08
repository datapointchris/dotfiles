-- Workspace configuration
-- See https://wiki.hypr.land/Configuring/Basics/Workspace-Rules/
-- Persistent named workspaces (always visible in waybar)

hl.workspace_rule({ workspace = 'name:A', persistent = true, default = true })
for _, name in ipairs({ 'B', 'D', 'E', 'M', 'S', 'X', 'Z' }) do
  hl.workspace_rule({ workspace = 'name:' .. name, persistent = true })
end

-- Second desk monitor. Not persistent — it should stay out of waybar while that
-- output is disabled, which is nearly all the time.
hl.workspace_rule({ workspace = '9', monitor = 'HDMI-A-1' })
