-- Buffer any notifications emitted during startup and replay them once the
-- notifier (fidget) is ready, so early messages are readable and land in the
-- notification history rather than flashing past. Must run before the first
-- vim.notify below.
require('core.early-notify')()

local profiles = require('core.profiles')

-- Always load core configuration
require('core.options')
require('core.filetypes') -- before lazy, so the first buffer is already detected
require('core.lazy') -- Load lazy.nvim in both VSCode and Neovim
require('core.keymaps')

if not profiles.is_vscode then
  -- Native ui2 message/cmdline UI. VSCode owns its own UI.
  require('core.ui2')
  require('core.autocmds')
  -- Custom floating terminal (Space t t). VSCode has its own terminal.
  require('core.floaterminal')
  require('lsp')
end
