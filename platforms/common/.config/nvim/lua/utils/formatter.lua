-- Unified formatter module
local M = {}

-- Formatter configuration: maps filetypes to external formatters (matching pre-commit)
M.external_formatters = {
  lua = { cmd = 'stylua', args = {} },
  python = { cmd = 'ruff', args = { 'format', '--stdin-filename' } },
  javascript = { cmd = 'prettier', args = { '--stdin-filepath' } },
  typescript = { cmd = 'prettier', args = { '--stdin-filepath' } },
  json = { cmd = 'prettier', args = { '--stdin-filepath' } },
  yaml = { cmd = 'prettier', args = { '--stdin-filepath' } },
  markdown = { cmd = 'prettier', args = { '--stdin-filepath' } },
  css = { cmd = 'prettier', args = { '--stdin-filepath' } },
  html = { cmd = 'prettier', args = { '--stdin-filepath' } },
  sh = { cmd = 'shfmt', args = { '-i', '2' } },
  bash = { cmd = 'shfmt', args = { '-i', '2' } },
  go = { cmd = 'gofmt', args = {} },
  rust = { cmd = 'rustfmt', args = {} },
}

local function format_with_external(formatter, file_path)
  local cmd = formatter.cmd
  local args = vim.list_extend({}, formatter.args) -- Copy args

  -- Check if formatter is available
  if vim.fn.executable(cmd) ~= 1 then return false, cmd .. ' not found' end

  -- For formatters that work in-place (like stylua, rustfmt, gofmt)
  if cmd == 'stylua' or cmd == 'rustfmt' or cmd == 'gofmt' then
    table.insert(args, file_path)
    local result = vim.fn.system(cmd .. ' ' .. table.concat(args, ' '))
    if vim.v.shell_error == 0 then
      vim.cmd('checktime') -- Reload file
      return true, 'Formatted with ' .. cmd
    else
      return false, cmd .. ' failed: ' .. result
    end

  -- For formatters that need stdin/stdout (like prettier, ruff format)
  elseif cmd == 'prettier' or (cmd == 'ruff' and vim.tbl_contains(args, 'format')) then
    -- Add filename to args for prettier/ruff
    table.insert(args, file_path)

    -- Read file content
    local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
    local content = table.concat(lines, '\n')

    -- Run formatter
    local full_cmd = cmd .. ' ' .. table.concat(args, ' ')
    local result = vim.fn.system(full_cmd, content)

    if vim.v.shell_error == 0 then
      -- Replace buffer content with formatted result
      local formatted_lines = vim.split(result, '\n')
      -- Remove trailing empty line if it exists
      if formatted_lines[#formatted_lines] == '' then table.remove(formatted_lines) end
      vim.api.nvim_buf_set_lines(0, 0, -1, false, formatted_lines)
      return true, 'Formatted with ' .. cmd
    else
      return false, cmd .. ' failed: ' .. result
    end

  -- For other formatters that work in-place (like shfmt)
  else
    table.insert(args, file_path)
    local result = vim.fn.system(cmd .. ' ' .. table.concat(args, ' '))
    if vim.v.shell_error == 0 then
      vim.cmd('checktime')
      return true, 'Formatted with ' .. cmd
    else
      return false, cmd .. ' failed: ' .. result
    end
  end
end

-- Main format function that tries external first, falls back to LSP
function M.format_buffer(opts)
  opts = opts or {}
  local show_notifications = opts.show_notifications ~= false
  local filetype = vim.bo.filetype
  local file_path = vim.fn.expand('%:p')

  -- Check if we have an external formatter for this filetype
  local formatter = M.external_formatters[filetype]
  if formatter then
    local success, message = format_with_external(formatter, file_path)
    if success then
      if show_notifications then vim.notify(message, vim.log.levels.INFO) end
      return true
    else
      if show_notifications then vim.notify(message .. ', falling back to LSP', vim.log.levels.WARN) end
    end
  end

  -- Fall back to LSP formatting
  vim.lsp.buf.format({ async = opts.async or false, timeout_ms = opts.timeout_ms or 1000 })
  return true
end

return M
