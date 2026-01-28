-- ================================================================== --
-- Environment Validation
-- ================================================================== --
-- Validate required environment variables for proper configuration
local required_env_vars = {
  'PLATFORM',
}

local missing_vars = {}
for _, var in ipairs(required_env_vars) do
  if not vim.env[var] then
    table.insert(missing_vars, var)
  end
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
  require('core.autocmds')
end

if profiles.is_full then
  require('lsp')
end
