-- Set the leader key to space
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- Show line numbers
vim.opt.number = true
-- Show relative line numbers
vim.opt.relativenumber = true
-- Minimal number of screen lines to keep above and below the cursor
vim.opt.scrolloff = 10

-- Set the window title
vim.opt.title = true

-- Number of spaces that a <Tab> in the file counts for
vim.opt.tabstop = 2
-- Number of spaces that a <Tab> counts for while performing editing operations
vim.opt.softtabstop = 2
-- Number of spaces to use for each step of (auto)indent
vim.opt.shiftwidth = 2
-- Use spaces instead of tabs
vim.opt.expandtab = true
-- Copy indent from the current line when starting a new line
vim.opt.autoindent = true
-- Do smart autoindenting when starting a new line
vim.opt.smartindent = true

-- Enable smart case search
vim.opt.smartcase = true
-- Highlight all matches of the previous search pattern
vim.opt.hlsearch = true

-- Disable line wrapping
vim.opt.wrap = false

-- Disable swap file creation
vim.opt.swapfile = false
-- Disable backup file creation
vim.opt.backup = false
-- Set the directory for undo files
vim.opt.undodir = os.getenv('HOME') .. '/.vim/undodir'
-- Enable persistent undo
vim.opt.undofile = true

-- Enable mouse support in all modes
vim.opt.mouse = 'a'

-- HOORAY! This is working on WSL2 using Ubuntu 24.04 and Windows 11 (2025-10-21)
vim.g.clipboard = {
  name = 'win32yank-wsl',
  copy = {
    ['+'] = 'win32yank.exe -i --crlf',
    ['*'] = 'win32yank.exe -i --crlf',
  },
  paste = {
    ['+'] = 'win32yank.exe -o --lf',
    ['*'] = 'win32yank.exe -o --lf',
  },
  cache_enable = 0,
}
vim.opt.clipboard = 'unnamedplus'

-- Open new split windows below the current window
vim.opt.splitbelow = true
-- Open new vertical split windows to the right of the current window
vim.opt.splitright = true
-- Keep the cursor in the same relative position when splitting windows
vim.opt.splitkeep = 'cursor'

-- Set the timeout length for mapped sequences (in milliseconds)
vim.o.timeoutlen = 300
-- Set the timeout length for key code sequences (in milliseconds)
vim.o.ttimeoutlen = 10

-- vim.lsp.set_log_level("debug")
