-- Autostart applications
-- See https://wiki.hypr.land/Configuring/Basics/Autostart/
--
-- hyprland.start fires once per session, so a config reload never relaunches these.

hl.on('hyprland.start', function()
  -- Update environment for portals
  hl.exec_cmd('dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP')

  -- Start on workspace A (before launching apps)
  hl.dispatch(hl.dsp.focus({ workspace = 'name:A' }))

  -- Polkit authentication agent
  hl.exec_cmd('/usr/lib/polkit-kde-authentication-agent-1')

  -- Status bar
  hl.exec_cmd('waybar')

  -- Notification daemon
  hl.exec_cmd('dunst')

  -- Clipboard manager (store text and image clipboard history)
  hl.exec_cmd('wl-paste --type text --watch cliphist store')
  hl.exec_cmd('wl-paste --type image --watch cliphist store')

  -- Idle daemon (dims, then turns the display off)
  hl.exec_cmd('hypridle')

  -- Wallpaper daemon (managed by theme system)
  hl.exec_cmd('hyprpaper')

  -- GTK settings for dark mode
  hl.exec_cmd('gsettings set org.gnome.desktop.interface color-scheme prefer-dark')
end)
