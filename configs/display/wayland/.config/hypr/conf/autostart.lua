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

  -- Status bar. playerctld must own its bus name before waybar starts. In waybar 0.15.0, the mpris module
  -- otherwise activates it, then leaks a player whose handlers outlive the module. After any bar teardown
  -- (a monitor disconnect, a SIGUSR2 reload), the next player event segfaults waybar.
  -- Upstream fixed this in Alexays/Waybar a8162186. Drop the busctl call once a release after 0.15.0 ships it.
  local start_playerctld = 'busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus '
    .. 'StartServiceByName su org.mpris.MediaPlayer2.playerctld 0'
  hl.exec_cmd(start_playerctld .. '; waybar')

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
