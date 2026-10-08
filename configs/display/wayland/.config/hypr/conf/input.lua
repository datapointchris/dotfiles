-- Input configuration
-- See https://wiki.hypr.land/Configuring/Basics/Variables/#input

hl.config({
  input = {
    kb_layout = 'us',
    kb_variant = '',
    kb_model = '',
    kb_options = '',
    kb_rules = '',
    numlock_by_default = true,

    -- Cursor focus detached from keyboard focus: hover scrolls, click types.
    follow_mouse = 2,

    sensitivity = 0, -- -1.0 to 1.0, 0 means no modification

    -- Touchpad settings (for laptop use if needed)
    touchpad = {
      natural_scroll = false,
      disable_while_typing = true,
      tap_to_click = true,
    },
  },

  cursor = {
    no_hardware_cursors = false,
  },
})
