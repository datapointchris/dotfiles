-- Auto-generated palette from theme.yml
-- Theme: Black Metal (Mayhem)
-- Source: Ghostty built-in theme

local M = {}

M.palette = {
  -- Base16 palette
  base00 = '#000000',
  base01 = '#3f3f3f',
  base02 = '#c1c1c1',
  base03 = '#3f3f3f',
  base04 = '#c1c1c1',
  base05 = '#c1c1c1',
  base06 = '#c1c1c1',
  base07 = '#c1c1c1',
  base08 = '#5f8787',
  base09 = '#5f8787',
  base0A = '#eecc6c',
  base0B = '#f3ecd4',
  base0C = '#aaaaaa',
  base0D = '#888888',
  base0E = '#999999',
  base0F = '#999999',
}

M.special = {
  background = '#000000',
  foreground = '#c1c1c1',
  cursor = '#c1c1c1',
  cursor_text = '#c1c1c1',
  selection_bg = '#c1c1c1',
  selection_fg = '#000000',
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
