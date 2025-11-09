local M = {}

local workflows = {
  ['File Navigation'] = {
    description = 'Finding and opening files',
    commands = {
      { key = '<leader>ff', desc = 'Find files' },
      { key = '<leader>fg', desc = 'Live grep (search in files)' },
      { key = '<leader>fb', desc = 'Show open buffers' },
      { key = '<leader>fr', desc = 'Show registers' },
      { key = '<leader>fn', desc = 'Search nvim config files' },
      { key = '\\', desc = 'NeoTree reveal current file' },
      { key = '<leader>tt', desc = 'Toggle file tree' },
      { key = '-', desc = 'Oil: Open parent directory' },
    },
  },

  ['Obsidian/Notes'] = {
    description = 'Working with your notes and Obsidian',
    commands = {
      { key = '<leader>ot', desc = 'Create new note from template' },
      { key = '<leader>os', desc = 'Search Obsidian notes' },
      { key = '<leader>oq', desc = 'Quick switch between notes' },
      { key = '<leader>on', desc = 'Create new note' },
      { key = '<leader>oo', desc = 'Open in Obsidian app' },
      { key = '<leader>ol', desc = 'Show note links' },
      { key = '<leader>ob', desc = 'Show backlinks' },
      { key = '<leader>oc', desc = 'Toggle checkbox' },
      { key = '<leader>sn', desc = 'Search notes (custom function)' },
    },
  },

  ['Code Intelligence (LSP)'] = {
    description = 'Navigation and code understanding',
    commands = {
      { key = 'gd', desc = 'Go to definition' },
      { key = 'gr', desc = 'Go to references' },
      { key = 'gI', desc = 'Go to implementation' },
      { key = 'gD', desc = 'Go to declaration' },
      { key = '<leader>D', desc = 'Type definition' },
      { key = '<leader>rn', desc = 'Rename symbol' },
      { key = '<leader>ca', desc = 'Code actions' },
      { key = '<leader>ds', desc = 'Document symbols' },
      { key = '<leader>ws', desc = 'Workspace symbols' },
      { key = '<leader>fmt', desc = 'Format buffer' },
      { key = '<leader>fmi', desc = 'Fix all linting issues' },
    },
  },

  ['AI/Copilot'] = {
    description = 'GitHub Copilot and AI assistance',
    commands = {
      { key = '<leader>cct', desc = 'Toggle Copilot Chat' },
      { key = '<leader>cca', desc = 'Ask Copilot' },
      { key = '<leader>ccd', desc = 'Fix diagnostic with Copilot' },
      { key = '<leader>ccr', desc = 'Reset Copilot chat' },
      { key = '<leader>cch', desc = 'Show Copilot help actions' },
      { key = '<leader>ccp', desc = 'Show Copilot prompts' },
      { key = '<leader>ccba', desc = 'Ask about current buffer' },
      { key = '<leader>ccbe', desc = 'Explain current buffer' },
      { key = '<leader>ccbr', desc = 'Refactor current buffer' },
      { key = '<leader>ccbt', desc = 'Write tests for buffer' },
    },
  },

  ['Debugging'] = {
    description = 'Debug your code',
    commands = {
      { key = '<F5>', desc = 'Start/Continue debugging' },
      { key = '<F1>', desc = 'Step into' },
      { key = '<F2>', desc = 'Step over' },
      { key = '<F3>', desc = 'Step out' },
      { key = '<leader>b', desc = 'Toggle breakpoint' },
      { key = '<leader>B', desc = 'Set conditional breakpoint' },
      { key = '<F7>', desc = 'Toggle debug UI' },
    },
  },

  ['Window/Buffer Management'] = {
    description = 'Managing windows, tabs, and buffers',
    commands = {
      { key = '<C-h/j/k/l>', desc = 'Navigate between windows/tmux panes' },
      { key = '<leader><C-_>', desc = 'Split window horizontally' },
      { key = '<leader><C_|>', desc = 'Split window vertically' },
      { key = '<C-Left/Right/Up/Down>', desc = 'Resize windows' },
      { key = '<tab>', desc = 'Next tab' },
      { key = '<s-tab>', desc = 'Previous tab' },
      { key = 'te', desc = 'Tab edit (new tab)' },
      { key = 'tw', desc = 'Tab close' },
      { key = '<leader>sm', desc = 'Maximize/minimize split' },
      { key = 'gb', desc = 'Open buffer menu (Snipe)' },
    },
  },

  ['Git'] = {
    description = 'Git operations and version control',
    commands = {
      { key = '<leader>tg', desc = 'Git status in floating tree' },
      { key = '<leader>ccgm', desc = 'Generate commit message with Copilot' },
      { key = 'gx', desc = 'Open URL/link under cursor' },
    },
  },

  ['Text Editing'] = {
    description = 'Text manipulation and editing',
    commands = {
      { key = '<leader>p', desc = 'Replace selection with yanked text' },
      { key = '<leader>d', desc = 'Delete without yanking' },
      { key = '<leader>y', desc = 'Yank to system clipboard' },
      { key = '<leader>Y', desc = 'Yank line to system clipboard' },
      { key = '<leader>p', desc = 'Paste from system clipboard' },
      { key = 'J/K (visual)', desc = 'Move selected text up/down' },
      { key = '+/-', desc = 'Increment/decrement number' },
      { key = 'x', desc = 'Cut to black hole register' },
      { key = '<C-a>', desc = 'Select all' },
    },
  },

  ['Search & Replace'] = {
    description = 'Finding and replacing text',
    commands = {
      { key = '<Esc>', desc = 'Clear search highlights' },
      { key = '<cmd>cn/cp', desc = 'Navigate quickfix list' },
      { key = '<cmd>ln/lp', desc = 'Navigate location list' },
      { key = '<leader>xx', desc = 'Show buffer diagnostics' },
      { key = '<leader>xw', desc = 'Show workspace diagnostics' },
      { key = '<leader>xt', desc = 'Show TODO comments' },
    },
  },

  ['Appearance & UI'] = {
    description = 'Customizing the interface',
    commands = {
      { key = '<leader>fz', desc = 'Color scheme picker' },
      { key = '<leader>z', desc = 'Toggle Zen mode' },
      { key = '<leader>?', desc = 'Show buffer-local keymaps' },
    },
  },

  ['Quick Exit'] = {
    description = 'Saving and quitting',
    commands = {
      { key = '<leader>qq', desc = 'Quit current buffer' },
      { key = '<leader>qa', desc = 'Quit all' },
      { key = '<leader>qs', desc = 'Save and quit' },
      { key = '<leader>qx', desc = 'Save all and quit' },
      { key = '<leader>qQ', desc = 'Quit without saving' },
      { key = '<leader>QQ', desc = 'Force quit all without saving' },
    },
  },
}

function M.show_workflow_picker()
  local actions = require('telescope.actions')
  local action_state = require('telescope.actions.state')
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')

  -- Create workflow list
  local workflow_list = {}
  for name, workflow in pairs(workflows) do
    table.insert(workflow_list, {
      name = name,
      description = workflow.description,
      commands = workflow.commands,
    })
  end

  pickers
    .new({}, {
      prompt_title = 'Neovim Workflows',
      finder = finders.new_table({
        results = workflow_list,
        entry_maker = function(entry)
          return {
            value = entry,
            display = string.format('%-25s %s', entry.name, entry.description),
            ordinal = entry.name .. ' ' .. entry.description,
          }
        end,
      }),
      sorter = conf.generic_sorter({}),
      previewer = previewers.new_buffer_previewer({
        title = 'Commands',
        define_preview = function(self, entry, status)
          local workflow = entry.value
          local lines = {
            '# ' .. workflow.name,
            '',
            workflow.description,
            '',
            '## Commands:',
            '',
          }

          for _, cmd in ipairs(workflow.commands) do
            table.insert(lines, string.format('%-20s %s', cmd.key, cmd.desc))
          end

          vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, lines)
          vim.api.nvim_buf_set_option(self.state.bufnr, 'filetype', 'markdown')
        end,
      }),
      attach_mappings = function(prompt_bufnr, map)
        actions.select_default:replace(function()
          local selection = action_state.get_selected_entry()
          actions.close(prompt_bufnr)
          M.show_workflow_commands(selection.value)
        end)
        return true
      end,
    })
    :find()
end

function M.show_workflow_commands(workflow)
  local lines = {
    '# ' .. workflow.name,
    '',
    workflow.description,
    '',
    '## Commands:',
    '',
  }

  for _, cmd in ipairs(workflow.commands) do
    table.insert(lines, string.format('%-25s %s', cmd.key, cmd.desc))
  end

  -- Create floating window
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.api.nvim_buf_set_option(buf, 'filetype', 'markdown')
  vim.api.nvim_buf_set_option(buf, 'modifiable', false)

  local width = math.min(100, vim.o.columns - 4)
  local height = math.min(#lines + 2, vim.o.lines - 4)

  local opts = {
    relative = 'editor',
    width = width,
    height = height,
    col = (vim.o.columns - width) / 2,
    row = (vim.o.lines - height) / 2,
    style = 'minimal',
    border = 'rounded',
    title = ' ' .. workflow.name .. ' ',
    title_pos = 'center',
  }

  local win = vim.api.nvim_open_win(buf, true, opts)

  -- Set up keymaps for the floating window
  local keymaps = {
    ['q'] = '<cmd>close<cr>',
    ['<Esc>'] = '<cmd>close<cr>',
  }

  for key, cmd in pairs(keymaps) do
    vim.api.nvim_buf_set_keymap(buf, 'n', key, cmd, { noremap = true, silent = true })
  end
end

function M.show_all_keymaps()
  local all_commands = {}

  for workflow_name, workflow in pairs(workflows) do
    for _, cmd in ipairs(workflow.commands) do
      table.insert(all_commands, {
        workflow = workflow_name,
        key = cmd.key,
        desc = cmd.desc,
      })
    end
  end

  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values

  pickers
    .new({}, {
      prompt_title = 'All Keymaps',
      finder = finders.new_table({
        results = all_commands,
        entry_maker = function(entry)
          return {
            value = entry,
            display = string.format('%-20s %-25s %s', entry.key, '[' .. entry.workflow .. ']', entry.desc),
            ordinal = entry.key .. ' ' .. entry.desc .. ' ' .. entry.workflow,
          }
        end,
      }),
      sorter = conf.generic_sorter({}),
    })
    :find()
end

return M
