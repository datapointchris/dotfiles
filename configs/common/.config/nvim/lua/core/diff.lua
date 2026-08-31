-- Diff appearance, normalised across every colorscheme.
--
-- Neovim's four diff groups are set by whichever colorscheme is loaded, and the
-- results are not comparable. Measured across fifteen of the themes in the
-- library: slate paints added lines #5f875f and deleted lines a saturated
-- magenta, carbonfox tints them so faintly they read as unchanged, and
-- OceanicNext gives all four groups one identical grey and separates them by a
-- foreground alone. Eight of the fifteen set that foreground, which overrides
-- treesitter and flattens a whole hunk to one shade.
--
-- The `theme` tool already solved this for the command line. `delta.sh` blends
-- the accent toward the background until the result clears a target contrast
-- ratio, rather than blending by a fixed fraction that lands somewhere different
-- on every palette. `band` below is that same solve, against the live highlight
-- table instead of theme.yml, which is what reaches the nineteen themes whose
-- colours come from a plugin the tool does not generate.
--
-- The targets are delta's: 1.45:1 for a changed line, 2.2:1 for the emphasis
-- inside it. DiffChange marks the line and DiffText marks the characters that
-- actually differ, so they take the line and emphasis targets respectively.

-- Deleted lines occupy no row on the far side of a diff, and the placeholder is
-- blank rather than a rule of '-' across the width. Every other fillchars item
-- keeps its default: omitted items fall back one at a time.
vim.opt.fillchars:append({ diff = ' ' })

local LINE_CONTRAST = 1.45
local EMPHASIS_CONTRAST = 2.2

local function channels(n) return { math.floor(n / 65536) % 256, math.floor(n / 256) % 256, n % 256 } end

local function linear(value)
  local c = value / 255
  if c <= 0.03928 then return c / 12.92 end
  return ((c + 0.055) / 1.055) ^ 2.4
end

local function luminance(c) return 0.2126 * linear(c[1]) + 0.7152 * linear(c[2]) + 0.0722 * linear(c[3]) end

local function contrast(a, b)
  if a > b then return (a + 0.05) / (b + 0.05) end
  return (b + 0.05) / (a + 0.05)
end

local function mix(accent, background, fraction)
  local out = {}
  for i = 1, 3 do
    out[i] = accent[i] * fraction + background[i] * (1 - fraction)
  end
  return out
end

-- Capped at 0.65 so an accent already close to the background cannot resolve to
-- an opaque slab.
local function band(accent, background, target)
  local a, b = channels(accent), channels(background)
  local base = luminance(b)
  local fraction = 0.65
  local f = 0.02
  while f <= 0.65 do
    if contrast(luminance(mix(a, b, f)), base) >= target then
      fraction = f
      break
    end
    f = f + 0.01
  end
  local c = mix(a, b, fraction)
  return string.format('#%02x%02x%02x', math.floor(c[1] + 0.5), math.floor(c[2] + 0.5), math.floor(c[3] + 0.5))
end

local function resolved(group)
  local ok, hl = pcall(vim.api.nvim_get_hl, 0, { name = group, link = false })
  if not ok or type(hl) ~= 'table' then return {} end
  return hl
end

local function apply()
  -- Added/Removed/Changed are Neovim's own semantic VCS groups, so a theme with
  -- an opinion supplies it and one without still yields a usable hue. They are
  -- foregrounds, which is what gives the solve headroom to reach its target: a
  -- theme's existing diff background can sit below the target already, and no
  -- blend fraction would then lift it.
  local add = resolved('Added').fg
  local delete = resolved('Removed').fg
  local change = resolved('Changed').fg
  if not (add and delete and change) then return end

  -- A theme may leave Normal's background to the terminal (solarized-osaka), and
  -- there is no way to read what the terminal chose.
  local bg = resolved('Normal').bg or (vim.o.background == 'dark' and 0x000000 or 0xffffff)

  vim.api.nvim_set_hl(0, 'DiffAdd', { bg = band(add, bg, LINE_CONTRAST) })
  vim.api.nvim_set_hl(0, 'DiffDelete', { bg = band(delete, bg, LINE_CONTRAST) })
  vim.api.nvim_set_hl(0, 'DiffChange', { bg = band(change, bg, LINE_CONTRAST) })
  vim.api.nvim_set_hl(0, 'DiffText', { bg = band(change, bg, EMPHASIS_CONTRAST) })

  -- Diffview copies DiffDelete into DiffviewDiffAddAsDelete, which is the group
  -- that paints removed lines in its left pane, and it reads the colours rather
  -- than linking to them. Its own ColorScheme handler registers when the plugin
  -- lazy-loads, so it already runs after this one; the call is here so the
  -- result does not depend on that ordering.
  local loaded, hl = pcall(require, 'diffview.hl')
  if loaded then pcall(hl.update_diff_hl) end
end

vim.api.nvim_create_autocmd('ColorScheme', {
  desc = 'Diff: solve the diff groups against the incoming theme',
  group = vim.api.nvim_create_augroup('diff-colours', { clear = true }),
  pattern = '*',
  callback = apply,
})

apply()
