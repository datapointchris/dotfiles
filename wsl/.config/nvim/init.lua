-- Always load core configuration
require('core.options')
require('core.lazy') -- Load lazy.nvim in both VSCode and Neovim
require('core.keymaps')

-- Only load autocmds in regular Neovim
if not vim.g.vscode then require('core.autocmds') end
