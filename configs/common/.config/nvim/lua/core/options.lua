vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

local venv_python = vim.fn.getcwd() .. '/.venv/bin/python'
if vim.fn.executable(venv_python) == 1 then vim.g.python3_host_prog = venv_python end

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.scrolloff = 10

vim.opt.title = true
vim.o.winborder = 'rounded'
vim.opt.cmdheight = 0

vim.opt.tabstop = 2
vim.opt.softtabstop = 2
vim.opt.shiftwidth = 2
vim.opt.expandtab = true
vim.opt.autoindent = true
vim.opt.smartindent = true

vim.opt.smartcase = true
vim.opt.hlsearch = true

vim.opt.wrap = false

-- Folding via the native treesitter fold expression (no plugin). foldexpr
-- returns 0 for buffers without a parser, so it is safe as a global default.
-- foldlevelstart = 99 opens files fully unfolded — folds are available on
-- demand (za / zM / zR) but never applied automatically on open.
vim.o.foldmethod = 'expr'
vim.o.foldexpr = 'v:lua.vim.treesitter.foldexpr()'
vim.o.foldlevelstart = 99

vim.opt.swapfile = false
vim.opt.backup = false
local undodir = os.getenv('XDG_STATE_HOME') or (os.getenv('HOME') .. '/.local/state')
vim.opt.undodir = undodir .. '/nvim/undo'
vim.fn.mkdir(vim.opt.undodir:get()[1], 'p')
vim.opt.undofile = true

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

vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.splitkeep = 'cursor'

vim.o.timeoutlen = 300
vim.o.ttimeoutlen = 10

vim.o.sessionoptions = 'blank,buffers,curdir,folds,help,tabpages,winsize,winpos,terminal,localoptions'
