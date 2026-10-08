-- Hyprland configuration
-- See https://wiki.hypr.land/Configuring/Start/
--
-- `require('conf.x')` resolves to conf/x.lua beside this file: Hyprland puts its
-- own config directory first on package.path.

-- Environment variables for Wayland compatibility
hl.env('XDG_CURRENT_DESKTOP', 'Hyprland')
hl.env('XDG_SESSION_TYPE', 'wayland')
hl.env('XDG_SESSION_DESKTOP', 'Hyprland')

-- Qt Wayland
hl.env('QT_QPA_PLATFORM', 'wayland;xcb')
hl.env('QT_WAYLAND_DISABLE_WINDOWDECORATION', '1')
hl.env('QT_AUTO_SCREEN_SCALE_FACTOR', '1')

-- GTK
hl.env('GDK_BACKEND', 'wayland,x11,*')

-- Cursor
hl.env('XCURSOR_SIZE', '24')

-- Default terminal
hl.env('TERMINAL', 'ghostty')

require('conf.monitors')
require('conf.workspaces')
require('conf.input')
require('conf.appearance')

-- Written by `theme apply`, and loaded after appearance on purpose: it sets the
-- border and group colors again, so the theme's win. pcall swallows only the
-- module-not-found error, so a machine that has never applied a theme keeps
-- appearance's colors, while a broken theme file still reaches the error overlay.
pcall(require, 'themes.current')

require('conf.keybindings')
require('conf.windowrules')
require('conf.autostart')
