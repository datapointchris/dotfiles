-- Appearance configuration: decorations, animations, layouts
-- See https://wiki.hypr.land/Configuring/Basics/Variables/

hl.config({
  general = {
    gaps_in = 5,
    gaps_out = 5,
    border_size = 2,

    col = {
      active_border = { colors = { 'rgba(7e9cd8ee)', 'rgba(957fb8ee)' }, angle = 45 },
      inactive_border = 'rgba(54546daa)',
    },

    layout = 'dwindle',
    resize_on_border = true,
  },

  decoration = {
    rounding = 10,

    active_opacity = 1.0,
    inactive_opacity = 0.92,

    shadow = {
      enabled = true,
      range = 20,
      render_power = 3,
      color = 'rgba(16161dee)',
    },

    blur = {
      enabled = true,
      size = 8,
      passes = 2,
      new_optimizations = true,
      ignore_opacity = true,
    },
  },

  animations = {
    enabled = true,
  },

  dwindle = {
    preserve_split = true,
    force_split = 2,
  },

  misc = {
    disable_hyprland_logo = true,
    disable_splash_rendering = true,
    force_default_wallpaper = 0,
    mouse_move_enables_dpms = true,
    key_press_enables_dpms = true,
  },

  -- Disable ecosystem update notifications
  ecosystem = {
    no_update_news = true,
  },
})

-- See https://wiki.hypr.land/Configuring/Advanced-and-Cool/Animations/
hl.curve('ease', { type = 'bezier', points = { { 0.25, 0.1 }, { 0.25, 1 } } })
hl.curve('easeOut', { type = 'bezier', points = { { 0, 0 }, { 0.58, 1 } } })
hl.curve('easeInOut', { type = 'bezier', points = { { 0.42, 0 }, { 0.58, 1 } } })
hl.curve('overshot', { type = 'bezier', points = { { 0.05, 0.9 }, { 0.1, 1.1 } } })

hl.animation({ leaf = 'windows', enabled = true, speed = 5, bezier = 'overshot', style = 'slide' })
hl.animation({ leaf = 'windowsOut', enabled = true, speed = 5, bezier = 'easeOut', style = 'slide' })
hl.animation({ leaf = 'border', enabled = true, speed = 10, bezier = 'default' })
hl.animation({ leaf = 'borderangle', enabled = true, speed = 100, bezier = 'easeInOut', style = 'loop' })
hl.animation({ leaf = 'fade', enabled = true, speed = 5, bezier = 'ease' })
hl.animation({ leaf = 'workspaces', enabled = true, speed = 5, bezier = 'easeInOut', style = 'slide' })
hl.animation({ leaf = 'specialWorkspace', enabled = true, speed = 5, bezier = 'easeInOut', style = 'slidevert' })
