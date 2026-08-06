-- Centralized Neovim plugin profiles
-- Single source of truth for profile detection and plugin filtering
--
-- Profiles (checked in priority order):
--   vscode  - auto-detected when embedded in VSCode (vim.g.vscode)
--   minimal - a server, or NVIM_PROFILE=minimal explicitly
--   full    - default, everything loads
--
-- The profile follows MACHINE_ROLE rather than being a second variable that has
-- to be set by hand and kept in step: a machine that has already declared
-- itself a server has said everything needed to pick this. NVIM_PROFILE stays
-- as the override for the rarer case — a workstation that wants the lean set.

local M = {}

local function resolve_profile()
  local explicit = vim.env.NVIM_PROFILE
  if explicit and explicit ~= '' then return explicit end
  return vim.env.MACHINE_ROLE == 'server' and 'minimal' or 'full'
end

M.is_vscode = vim.g.vscode ~= nil
M.is_minimal = not M.is_vscode and resolve_profile() == 'minimal'
M.is_full = not M.is_vscode and not M.is_minimal

-- VSCode: these plugins are DISABLED (blocklist)
-- Everything not listed here loads in VSCode
local vscode_disabled = {
  -- UI chrome (VSCode has its own)
  ['lualine.nvim'] = true,
  ['bufferline.nvim'] = true,
  ['fidget.nvim'] = true,
  ['indent-blankline.nvim'] = true,
  ['dressing.nvim'] = true,
  ['snipe.nvim'] = true,
  -- Navigation (VSCode has native equivalents)
  ['telescope.nvim'] = true,
  ['telescope-fzf-native.nvim'] = true,
  ['telescope-ui-select.nvim'] = true,
  ['yazi.nvim'] = true,
  ['vim-tmux-navigator'] = true,
  -- Git (VSCode has built-in git)
  ['gitsigns.nvim'] = true,
  ['lazygit.nvim'] = true,
  ['diffview.nvim'] = true,
  ['diffbandit.nvim'] = true,
  -- Completion & LSP (VSCode handles these)
  ['blink.cmp'] = true,
  ['blink.lib'] = true,
  ['friendly-snippets'] = true,
  ['lazydev.nvim'] = true,
  -- Colorschemes (VSCode has its own theme manager)
  ['github-theme'] = true,
  ['rose-pine'] = true,
  ['kanagawa.nvim'] = true,
  ['gruvbox.nvim'] = true,
  ['nordic.nvim'] = true,
  ['nightfox.nvim'] = true,
  ['solarized-osaka.nvim'] = true,
  ['oceanic-next'] = true,
  ['flexoki-moon-nvim'] = true,
  ['everforest-nvim'] = true,
  ['colorscheme-manager'] = true,
  -- Sessions & editing features VSCode handles
  ['auto-session'] = true,
  ['cinnamon.nvim'] = true,
  ['conform.nvim'] = true,
  ['inc-rename.nvim'] = true,
  ['todo-comments.nvim'] = true,
  ['trouble.nvim'] = true,
  ['vim-maximizer'] = true,
  ['which-key.nvim'] = true,
  ['zen-mode.nvim'] = true,
  ['zk-nvim'] = true,
}

-- Minimal: only these plugins load (server editing essentials, allowlist)
local minimal_plugins = {
  -- Core
  ['mini.nvim'] = true,
  ['plenary.nvim'] = true,
  -- Navigation
  ['telescope.nvim'] = true,
  ['telescope-fzf-native.nvim'] = true,
  ['telescope-ui-select.nvim'] = true,
  ['yazi.nvim'] = true,
  ['vim-tmux-navigator'] = true,
  ['snipe.nvim'] = true,
  -- UI
  ['lualine.nvim'] = true,
  ['bufferline.nvim'] = true,
  ['fidget.nvim'] = true,
  ['dressing.nvim'] = true,
  ['indent-blankline.nvim'] = true,
  ['cinnamon.nvim'] = true,
  -- Editing
  ['which-key.nvim'] = true,
  ['vim-visual-multi'] = true,
  ['winresize.nvim'] = true,
  ['vim-maximizer'] = true,
  ['blink.cmp'] = true,
  ['blink.lib'] = true,
  ['friendly-snippets'] = true,
  -- Git
  ['gitsigns.nvim'] = true,
  ['diffview.nvim'] = true,
  -- Diagnostics
  ['trouble.nvim'] = true,
  ['todo-comments.nvim'] = true,
}

--- Plugin condition function for lazy.nvim defaults.cond
---@param plugin LazyPlugin
---@return boolean
function M.plugin_enabled(plugin)
  if M.is_vscode then return not vscode_disabled[plugin.name] end
  if M.is_minimal then return minimal_plugins[plugin.name] == true end
  return true
end

return M
