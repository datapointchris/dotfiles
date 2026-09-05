-- Set the leader key to space
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- The Python host runs remote plugins, so it has to be an interpreter carrying
-- `pynvim`. A project's own `.venv` is the wrong choice for it: almost none of
-- them install `pynvim`, so a remote plugin would work in some directories and
-- fail in others with nothing on screen saying why. The jupyterlab tool venv
-- carries `pynvim` and `jupyter_client` together, which is what molten needs.
--
-- A kernel is a separate process and is chosen per buffer, so nothing here
-- constrains which environment code actually runs in.
local data_home = vim.env.XDG_DATA_HOME or vim.fn.expand('~/.local/share')
local nvim_python = data_home .. '/uv/tools/jupyterlab/bin/python'
if vim.fn.executable(nvim_python) == 1 then vim.g.python3_host_prog = nvim_python end

-- Show line numbers
vim.opt.number = true
-- Show relative line numbers
vim.opt.relativenumber = true
-- Minimal number of screen lines to keep above and below the cursor
vim.opt.scrolloff = 10

-- Set the window title
vim.opt.title = true
-- Rounded borders for floating windows
vim.o.winborder = 'rounded'
-- Command line height
vim.opt.cmdheight = 0

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

-- Enable smart case search. smartcase only applies when ignorecase is on, so
-- the pair is the setting; \C in a pattern forces case-sensitivity back.
vim.opt.ignorecase = true
vim.opt.smartcase = true
-- Highlight all matches of the previous search pattern
vim.opt.hlsearch = true

-- Disable line wrapping
vim.opt.wrap = false

-- Folding via the native treesitter fold expression (no plugin). foldexpr
-- returns 0 for buffers without a parser, so it is safe as a global default.
-- foldlevelstart = 99 opens files fully unfolded — folds are available on
-- demand (za / zM / zR) but never applied automatically on open.
vim.o.foldmethod = 'expr'
vim.o.foldexpr = 'v:lua.vim.treesitter.foldexpr()'
vim.o.foldlevelstart = 99

-- Disable swap file creation
vim.opt.swapfile = false
-- Disable backup file creation
vim.opt.backup = false
-- Set the directory for undo files
local undodir = os.getenv('XDG_STATE_HOME') or (os.getenv('HOME') .. '/.local/state')
vim.opt.undodir = undodir .. '/nvim/undo'
-- Create undo directory if it doesn't exist
vim.fn.mkdir(vim.opt.undodir:get()[1], 'p')
-- Enable persistent undo
vim.opt.undofile = true

-- Enable mouse support in all modes
vim.opt.mouse = 'a'

-- Use win32yank if on wsl. WSL sets $WSL_DISTRO_NAME itself, so the answer comes
-- from the thing being detected rather than from a coordinate the machine had to
-- declare — which is what tmux.conf already does for this same clipboard.
if vim.env.WSL_DISTRO_NAME then
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
    cache_enabled = 0,
  }
end

-- Explicit clipboard model: keep Neovim's registers separate from the OS
-- clipboard so plain y/d/c/p stay internal and deletes never pollute clipboard
-- history. Reach the system clipboard deliberately via the <leader>y / <leader>p
-- maps (the `+` register). On WSL the provider above backs `+` with win32yank;
-- elsewhere Neovim's default pbcopy/xclip/wl provider is used. See the
-- clipboard-copy-paste workflow card.

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

vim.o.sessionoptions = 'blank,buffers,curdir,folds,help,tabpages,winsize,winpos,terminal,localoptions'
