-- Which kind of Neovim this is, and which plugins load in it. Two kinds load
-- less than the whole set: one embedded in VSCode through vscode-neovim, and one
-- prs started to show a pull request's diff.
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

-- prs starts nvim in a repo's checkout to show one pull request's diff, with
-- PRS_DIFF_DOCUMENT naming the pull request's markdown document and
-- PRS_DIFF_THREADS its review threads. Both are read once and cleared, so an
-- nvim started from this one, such as lazygit's editor, is an ordinary nvim.
local function taken(name)
  local value = vim.env[name]
  vim.env[name] = nil
  if value == nil or value == '' then
    return nil
  end
  return value
end

local document, threads = taken('PRS_DIFF_DOCUMENT'), taken('PRS_DIFF_THREADS')

---@type { document: string, threads: string? }?
M.pull_request_diff = document and { document = document, threads = threads } or nil

-- Each keeps state for the directory nvim started in, which in a pull request's
-- diff is the repo's own checkout.
local pull_request_diff_disabled = {
  -- Saving at exit would replace the repo's session with the diff's buffers,
  -- which are gone once nvim exits.
  ['auto-session'] = true,
}

--- Plugin condition function for lazy.nvim defaults.cond
---@param plugin LazyPlugin
---@return boolean
function M.plugin_enabled(plugin)
  if M.is_vscode then
    return vscode_enabled[plugin.name] == true
  end
  if M.pull_request_diff then
    return not pull_request_diff_disabled[plugin.name]
  end
  return true
end

return M
