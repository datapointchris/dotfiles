local wezterm = require('wezterm')
local config = wezterm.config_builder()

config.color_scheme = 'flexoki-dark'

config.enable_tab_bar = false

config.window_decorations = 'RESIZE'

config.window_background_opacity = 1.0
config.macos_window_background_blur = 10

config.font = wezterm.font('SeriousShanns Nerd Font Mono')
config.font_size = 17
config.cell_width = 1.1
config.line_height = 1.2

return config
