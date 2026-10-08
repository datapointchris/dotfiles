-- Window rules
-- See https://wiki.hypr.land/Configuring/Basics/Window-Rules/

hl.window_rule({
  name = 'float-dialogs',
  match = { title = '^(Open|Open File|Save As|Choose Files|Confirm|File Operation Progress)$' },
  float = true,
})

-- Float and center pavucontrol (audio settings)
hl.window_rule({
  name = 'pavucontrol',
  match = { class = '^(pavucontrol)$' },
  float = true,
  center = true,
})

-- Browser Picture-in-Picture (Firefox, Zen, Librewolf)
hl.window_rule({
  name = 'picture-in-picture',
  match = { title = '^(Picture-in-Picture)$' },
  float = true,
  pin = true,
  keep_aspect_ratio = true,
})

hl.window_rule({
  name = 'browser-sharing-indicator',
  match = { title = '(Sharing Indicator)$' },
  float = true,
  no_focus = true,
})

-- Prevent screen from turning off during fullscreen video
hl.window_rule({
  name = 'idle-inhibit-fullscreen-video',
  match = { class = '^(zen|vivaldi|firefox|mpv)$' },
  idle_inhibit = 'fullscreen',
})

-- Ghostty theme preview windows (float like on macOS)
hl.window_rule({
  name = 'ghostty-theme-preview',
  match = { class = '^(com.mitchellh.ghostty)$', title = '^(THEME PREVIEW:)(.*)$' },
  float = true,
})

hl.window_rule({
  name = 'polkit-dialog',
  match = { class = '^(org.kde.polkit-kde-authentication-agent-1)$' },
  float = true,
  center = true,
})

-- Rofi already floats; this keeps keyboard focus on it
hl.window_rule({
  name = 'rofi',
  match = { class = '^(Rofi)$' },
  stay_focused = true,
})
