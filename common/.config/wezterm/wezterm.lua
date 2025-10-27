local wezterm = require('wezterm')
local config = wezterm.config_builder()

config.color_scheme = 'flexoki-dark'

config.enable_tab_bar = false

config.window_decorations = 'RESIZE'

config.window_background_opacity = 1.0
config.macos_window_background_blur = 0 -- Disabled for performance on older hardware

-- Performance optimizations for 2018 Intel Mac Mini
config.max_fps = 60 -- Limit frame rate to reduce GPU load
config.animation_fps = 30 -- Reduce animation smoothness for better performance
config.scrollback_lines = 10000 -- Reduce from default to save memory

-- Rendering backend - OpenGL may perform better on older Intel GPUs
config.front_end = 'OpenGL'

-- Cursor performance optimizations
config.cursor_blink_ease_in = 'Constant'
config.cursor_blink_ease_out = 'Constant'
config.default_cursor_style = 'SteadyBlock' -- Disable blinking entirely

-- Font configuration
config.font = wezterm.font('SeriousShanns Nerd Font Mono', { weight = 'Regular' })
config.font_size = 17
config.cell_width = 1.1
config.line_height = 1.2
config.harfbuzz_features = {} -- Disable ligatures and font features for performance

return config
