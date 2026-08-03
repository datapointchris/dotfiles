-- Buffer any notifications emitted during startup and replay them once the
-- notifier (fidget) is ready, so early messages are readable and land in the
-- notification history rather than flashing past. Must run before the first
-- vim.notify below.
require('core.early-notify')()

-- ================================================================== --
-- Environment Validation
-- ================================================================== --
-- Validate required environment variables for proper configuration
local required_env_vars = {
  'PLATFORM',
}

local missing_vars = {}
for _, var in ipairs(required_env_vars) do
  if not vim.env[var] then table.insert(missing_vars, var) end
end

if #missing_vars > 0 then
  vim.notify(
    'Missing required environment variables: ' .. table.concat(missing_vars, ', ') .. '\nPlease check your ~/.env file',
    vim.log.levels.ERROR,
    { title = 'Environment Error' }
  )
end

local profiles = require('core.profiles')

-- Always load core configuration
require('core.options')
require('core.lazy') -- Load lazy.nvim in both VSCode and Neovim
require('core.keymaps')

if not profiles.is_vscode then
  -- Native ui2 message/cmdline UI (replaces noice). VSCode owns its own UI.
  require('core.ui2')
  require('core.autocmds')
  -- Custom floating terminal (Space t t). VSCode has its own terminal.
  require('core.floaterminal')
end

if profiles.is_full then require('lsp') end
