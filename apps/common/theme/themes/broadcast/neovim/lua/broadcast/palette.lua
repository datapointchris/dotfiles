-- Auto-generated palette from theme.yml
-- Theme: Broadcast
-- Source: Ghostty built-in theme

local M = {}

M.palette = {
  -- Base16 palette
  base00 = '#2b2b2b',
  base01 = '#585858',
  base02 = '#5a647e',
  base03 = '#585858',
  base04 = '#ffffff',
  base05 = '#e6e1dc',
  base06 = '#ffffff',
  base07 = '#ffffff',
  base08 = '#da4939',
  base09 = '#ff7b6b',
  base0A = '#ffd24a',
  base0B = '#519f50',
  base0C = '#6e9cbe',
  base0D = '#6d9cbe',
  base0E = '#d0d0ff',
  base0F = '#d0d0ff',
}

M.special = {
  background = '#2b2b2b',
  foreground = '#e6e1dc',
  cursor = '#ffffff',
  cursor_text = '#e6e1dc',
  selection_bg = '#5a647e',
  selection_fg = '#e6e1dc',
}

-- Semantic theme colors derived from palette
M.theme = {
  ui = {
    bg = M.palette.base00,
    bg_dim = M.palette.bg_dim or M.palette.base00,
    bg_p1 = M.palette.base01,
    bg_p2 = M.palette.base02,
    bg_m1 = M.palette.base01,
    bg_m3 = M.palette.base01,
    bg_gutter = M.palette.base00,
    bg_visual = M.palette.base02,
    bg_search = M.palette.base0A,
    fg = M.palette.base05,
    fg_dim = M.palette.base04,
    fg_reverse = M.palette.base00,
    special = M.palette.base0C,
    nontext = M.palette.base03,
    whitespace = M.palette.base02,
    float = {
      fg = M.palette.base05,
      bg = M.palette.base01,
      fg_border = M.palette.base04,
      bg_border = M.palette.base01,
    },
    pmenu = {
      fg = M.palette.base05,
      fg_sel = M.palette.base05,
      bg = M.palette.base01,
      bg_sel = M.palette.base02,
      bg_sbar = M.palette.base02,
      bg_thumb = M.palette.base03,
    },
  },
  syn = {
    comment = M.palette.base03,
    string = M.palette.base0B,
    number = M.palette.base0E,
    constant = M.palette.base0E,
    identifier = M.palette.base0D,
    parameter = M.palette.base0D,
    fun = M.palette.base0B,
    statement = M.palette.base08,
    keyword = M.palette.base08,
    operator = M.palette.base09,
    preproc = M.palette.base0C,
    type = M.palette.base0A,
    special1 = M.palette.base09,
    special2 = M.palette.base08,
    special3 = M.palette.base0C,
    punct = M.palette.base09,
    regex = M.palette.base0C,
    deprecated = M.palette.base03,
  },
  diag = {
    error = M.palette.base08,
    warning = M.palette.base09,
    info = M.palette.base0D,
    hint = M.palette.base0C,
    ok = M.palette.base0B,
  },
  vcs = {
    added = M.palette.base0B,
    changed = M.palette.base0A,
    removed = M.palette.base08,
  },
  diff = {
    add = M.palette.base0B,
    change = M.palette.base0A,
    delete = M.palette.base08,
    text = M.palette.base0D,
  },
}

return M
