local date_format = '%Y-%m-%d-%a'
local time_format = '%H:%M'
return {
  'epwalsh/obsidian.nvim',
  version = '*', -- recommended, use latest release instead of latest commit
  lazy = false,
  ft = 'markdown',
  -- Replace the above line with this if you only want to load obsidian.nvim for markdown files in your vault:
  -- event = {
  --   -- If you want to use the home shortcut '~' here you need to call 'vim.fn.expand'.
  --   -- E.g. "BufReadPre " .. vim.fn.expand "~" .. "/my-vault/*.md"
  --   -- refer to `:h file-pattern` for more examples
  --   "BufReadPre path/to/my-vault/*.md",
  --   "BufNewFile path/to/my-vault/*.md",
  -- },
  dependencies = { 'nvim-lua/plenary.nvim' },
  opts = {
    ui = { enable = false },
    workspaces = {
      {
        name = 'notes',
        path = '~/Documents/notes',
      },
    },
    notes_subdir = 'inbox',

    -- Optional, set the log level for obsidian.nvim. This is an integer corresponding to one of the log
    -- levels defined by "vim.log.levels.*".
    log_level = vim.log.levels.INFO,

    daily_notes = {
      -- Optional, if you keep daily notes in a separate directory.
      folder = 'dailies',
      -- Optional, if you want to change the date format for the ID of daily notes.
      date_format = date_format,
      -- Optional, if you want to change the date format of the default alias of daily notes.
      alias_format = '%B %-d, %Y',
      -- Optional, default tags to add to each new daily note created.
      default_tags = { 'daily-notes' },
      -- Optional, if you want to automatically insert a template from your template directory like 'daily.md'
      template = 'templates/daily.md',
    },
    new_notes_location = 'notes_subdir',
    note_id_func = function(title) return os.date(date_format .. '-' .. time_format) .. '-' .. title end,
    templates = {
      folder = 'templates',
      date_format = date_format,
      time_format = time_format,
      -- A map for custom variables, the key should be the variable and the value a function
      substitutions = {},
    },
  },
}
