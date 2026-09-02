-- Which plugins load, which is now only a question when Neovim is embedded in
-- VSCode through vscode-neovim. Everywhere else the whole set loads.
--
-- An allowlist rather than a blocklist, because the spec list is not fully
-- enumerable here: colorscheme-manager.lua synthesizes specs at startup by
-- scanning the theme library, so a blocklist cannot name what it has never
-- seen. That leaked — `cendre` and `sora` were loading in VSCode because
-- nobody thought to block them when those themes were added.
--
-- What earns a place: the plugin does something VSCode does not already do.
-- VSCode owns the chrome, the file tree, git, LSP, completion and the theme,
-- so none of that is here.

local M = {}

M.is_vscode = vim.g.vscode ~= nil

local vscode_enabled = {
  -- The manager itself, so `:Lazy` still works from inside VSCode.
  ['lazy.nvim'] = true,
  ['mini.nvim'] = true,
  ['plenary.nvim'] = true,
  ['nvim-treesitter'] = true,
  ['nvim-treesitter-textobjects'] = true,
  ['treesitter-modules.nvim'] = true,
  ['vim-visual-multi'] = true,
  ['markdown-toc.nvim'] = true,
  ['winresize.nvim'] = true,
  ['typos'] = true,
}

--- Plugin condition function for lazy.nvim defaults.cond
---@param plugin LazyPlugin
---@return boolean
function M.plugin_enabled(plugin)
  if M.is_vscode then return vscode_enabled[plugin.name] == true end
  return true
end

return M
