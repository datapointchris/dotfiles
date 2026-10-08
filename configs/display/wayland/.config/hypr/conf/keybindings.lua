-- Keybindings
-- Designed for consistency with macOS AeroSpace config
-- See https://wiki.hypr.land/Configuring/Basics/Binds/

local mainMod = 'SUPER'

-- rofi-keybinds lists only binds that carry a description, so the helper requires one.
local function bind(keys, description, dispatcher, opts)
  opts = opts or {}
  opts.description = description
  return hl.bind(keys, dispatcher, opts)
end

-- Applications
bind(mainMod .. ' + Return', 'Open terminal', hl.dsp.exec_cmd('ghostty'))
bind(mainMod .. ' + Space', 'Open launcher', hl.dsp.exec_cmd('rofi -show drun'))
bind(mainMod .. ' + SHIFT + slash', 'Show keybinds', hl.dsp.exec_cmd('rofi-keybinds'))

-- Window management
bind(mainMod .. ' + Q', 'Close window', hl.dsp.window.close())
bind(mainMod .. ' + F', 'Toggle floating', hl.dsp.window.float({ action = 'toggle' }))
-- maximized fills the workspace and keeps waybar and the gaps; fullscreen covers them
bind(mainMod .. ' + SHIFT + F', 'Toggle maximize', hl.dsp.window.fullscreen({ mode = 'maximized' }))

-- Focus navigation (vim-style)
bind(mainMod .. ' + H', 'Focus left', hl.dsp.focus({ direction = 'left' }))
bind(mainMod .. ' + J', 'Focus down', hl.dsp.focus({ direction = 'down' }))
bind(mainMod .. ' + K', 'Focus up', hl.dsp.focus({ direction = 'up' }))
bind(mainMod .. ' + L', 'Focus right', hl.dsp.focus({ direction = 'right' }))

-- Move windows (vim-style)
bind(mainMod .. ' + SHIFT + H', 'Move window left', hl.dsp.window.move({ direction = 'left' }))
bind(mainMod .. ' + SHIFT + J', 'Move window down', hl.dsp.window.move({ direction = 'down' }))
bind(mainMod .. ' + SHIFT + K', 'Move window up', hl.dsp.window.move({ direction = 'up' }))
bind(mainMod .. ' + SHIFT + L', 'Move window right', hl.dsp.window.move({ direction = 'right' }))

-- Join windows into group (vim-style)
bind(mainMod .. ' + CTRL + H', 'Join group left', hl.dsp.window.move({ into_group = 'left' }))
bind(mainMod .. ' + CTRL + J', 'Join group down', hl.dsp.window.move({ into_group = 'down' }))
bind(mainMod .. ' + CTRL + K', 'Join group up', hl.dsp.window.move({ into_group = 'up' }))
bind(mainMod .. ' + CTRL + L', 'Join group right', hl.dsp.window.move({ into_group = 'right' }))
bind(mainMod .. ' + CTRL + G', 'Toggle group', hl.dsp.group.toggle())

-- Named workspaces
for _, name in ipairs({ 'A', 'D', 'E', 'M', 'S', 'X', 'Z' }) do
  bind(mainMod .. ' + ' .. name, 'Go to workspace ' .. name, hl.dsp.focus({ workspace = 'name:' .. name }))
  bind(mainMod .. ' + SHIFT + ' .. name, 'Move to workspace ' .. name, hl.dsp.window.move({ workspace = 'name:' .. name }))
end
bind(mainMod .. ' + 9', 'Go to workspace 9 (second desk)', hl.dsp.focus({ workspace = 9 }))
bind(mainMod .. ' + SHIFT + 9', 'Move to workspace 9 (second desk)', hl.dsp.window.move({ workspace = 9 }))

-- Second desk monitor output
bind(mainMod .. ' + CTRL + W', 'Toggle second desk monitor', hl.dsp.exec_cmd('work-monitor'))

-- Workspace back-and-forth
bind(mainMod .. ' + Tab', 'Previous workspace', hl.dsp.focus({ workspace = 'previous' }))

-- Scratchpad (special workspace)
bind(mainMod .. ' + grave', 'Toggle scratchpad', hl.dsp.workspace.toggle_special('scratchpad'))
bind(mainMod .. ' + SHIFT + grave', 'Move to scratchpad', hl.dsp.window.move({ workspace = 'special:scratchpad', follow = false }))

-- Toggle split direction (matches AeroSpace tile orientation on alt-')
-- dwindle split toggle is a layout message, not a top-level dispatcher
bind(mainMod .. ' + apostrophe', 'Toggle split direction', hl.dsp.layout('togglesplit'))

-- Layout toggle (dwindle <-> master)
bind(mainMod .. ' + backslash', 'Toggle layout', function()
  local layout = hl.get_config('general.layout') == 'dwindle' and 'master' or 'dwindle'
  hl.config({ general = { layout = layout } })
end)

bind(mainMod .. ' + SHIFT + R', 'Reload config', hl.dsp.exec_cmd('hyprctl reload'))

-- Mouse bindings
bind(mainMod .. ' + mouse:272', 'Drag window', hl.dsp.window.drag())
bind(mainMod .. ' + mouse:273', 'Resize window', hl.dsp.window.resize())

-- Resize submap (mode)
bind(mainMod .. ' + R', 'Enter resize mode', hl.dsp.submap('resize'))

hl.define_submap('resize', function()
  bind('H', 'Shrink width', hl.dsp.window.resize({ x = -50, y = 0, relative = true }), { repeating = true })
  bind('J', 'Grow height', hl.dsp.window.resize({ x = 0, y = 50, relative = true }), { repeating = true })
  bind('K', 'Shrink height', hl.dsp.window.resize({ x = 0, y = -50, relative = true }), { repeating = true })
  bind('L', 'Grow width', hl.dsp.window.resize({ x = 50, y = 0, relative = true }), { repeating = true })
  bind('Escape', 'Leave resize mode', hl.dsp.submap('reset'))
  bind('Return', 'Leave resize mode', hl.dsp.submap('reset'))
end)

-- Media keys
bind('XF86AudioRaiseVolume', 'Volume up', hl.dsp.exec_cmd('wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+'), { repeating = true })
bind('XF86AudioLowerVolume', 'Volume down', hl.dsp.exec_cmd('wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-'), { repeating = true })
bind('XF86AudioMute', 'Mute audio', hl.dsp.exec_cmd('wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle'))
bind('XF86AudioMicMute', 'Mute microphone', hl.dsp.exec_cmd('wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle'))
bind('XF86AudioPlay', 'Play or pause', hl.dsp.exec_cmd('playerctl play-pause'))
bind('XF86AudioPrev', 'Previous track', hl.dsp.exec_cmd('playerctl previous'))
bind('XF86AudioNext', 'Next track', hl.dsp.exec_cmd('playerctl next'))

-- Brightness (if applicable)
bind('XF86MonBrightnessUp', 'Brightness up', hl.dsp.exec_cmd('brightnessctl s 10%+'), { repeating = true })
bind('XF86MonBrightnessDown', 'Brightness down', hl.dsp.exec_cmd('brightnessctl s 10%-'), { repeating = true })

-- Screenshot
bind('Print', 'Screenshot a region to the clipboard', hl.dsp.exec_cmd('grim -g "$(slurp)" - | wl-copy'))
bind(mainMod .. ' + Print', 'Screenshot the screen to the clipboard', hl.dsp.exec_cmd('grim - | wl-copy'))

-- Clipboard history
bind(mainMod .. ' + V', 'Clipboard history (select and paste)', hl.dsp.exec_cmd('rofi-clipboard'))
