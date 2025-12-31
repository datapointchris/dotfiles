-- Clear highlights on search when pressing <Esc> in normal mode
--  See `:help hlsearch`
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>', { desc = 'Clear highlights' })

-- Put single character cut text in the black hole register
vim.keymap.set('n', 'x', '"_x', { desc = 'Cut >> blackhole' })

-- Select all
vim.keymap.set('n', '<C-a>', 'gg<S-v>G', { desc = 'Select all' })

-- Reload neovim config or current line
vim.keymap.set('n', '<leader>rr', '<cmd>source ~/.config/nvim/init.lua<cr>')
vim.keymap.set('n', '<leader>rx', ':.lua<cr>')
vim.keymap.set('v', '<leader>rx', 'lua<cr>')

-- Move selected line / block of text in visual mode down / up
-- gv=gv reselects the text and reindents for proper formatting
vim.keymap.set('v', 'J', ":m '>+1<CR>gv=gv", { desc = 'Move selected text down' })
vim.keymap.set('v', 'K', ":m '<-2<CR>gv=gv", { desc = 'Move selected text up' })

-- Replace the selected text in visual mode
-- with the previously yanked or deleted text without overwriting the default register.
-- When you press `<leader>p` in visual mode, the selected text will be deleted and discarded
-- (sent to the black hole register), and the previously yanked or deleted text will be pasted in its place.
vim.keymap.set('x', '<leader>p', [["_dP]], { desc = 'Replace selected text with yanked text' })
vim.keymap.set({ 'n', 'v' }, '<leader>d', [["_d]], { desc = 'Delete without yanking' })

-- Yank text to the system clipboard in normal and visual modes
vim.keymap.set({ 'n', 'v' }, '<leader>y', [["+y]], { desc = 'Yank to system clipboard' })

-- Yank the entire line to the system clipboard in normal mode
vim.keymap.set('n', '<leader>Y', [["+Y]], { desc = 'Yank line to system clipboard' })

-- Paste text from the system clipboard
vim.keymap.set({ 'n', 'v' }, '<leader>p', [["+p]], { desc = 'Paste from system clipboard' })

-- Navigate the quickfix list
vim.keymap.set('n', '<cmd>cn', '<cmd>cnext<CR>zz', { desc = 'Navigate quickfix next' })
vim.keymap.set('n', '<cmd>cp', '<cmd>cprev<CR>zz', { desc = 'Navigate quickfix previous' })

-- Navigate the location list
vim.keymap.set('n', '<cmd>ln', '<cmd>lnext<CR>zz', { desc = 'Navigate location next' })
vim.keymap.set('n', '<cmd>lp', '<cmd>lprev<CR>zz', { desc = 'Navigate location previous' })

----------------------------------------
--- QUITTING -------------------------------
----------------------------------------
vim.keymap.set('n', '<leader>qq', ':q<CR>', { noremap = true, silent = true, desc = 'Quit: Current buffer' })
vim.keymap.set('n', '<leader>qa', ':qa<CR>', { noremap = true, silent = true, desc = 'Quit: All buffers' })
vim.keymap.set('n', '<leader>qs', ':wq<CR>', { noremap = true, silent = true, desc = 'Quit: Save and quit' })
vim.keymap.set('n', '<leader>qx', ':wqa<CR>', { noremap = true, silent = true, desc = 'Quit: Save all and quit' })
vim.keymap.set('n', '<leader>qQ', ':q!<CR>', { noremap = true, silent = true, desc = 'Quit: Force quit (no save)' })
vim.keymap.set('n', '<leader>QQ', ':qa!<CR>', { noremap = true, silent = true, desc = 'Quit: Force quit all (no save)' })

----------------------------------------
--- TABS -------------------------------
----------------------------------------
-- VSCode handles tabs natively, these conflict with VSCode tab navigation
-- Fixed: Moved 'te' and 'tw' to leader keys to avoid shadowing 't' motion
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>te', ':tabedit', { desc = 'Tab edit' })
  vim.keymap.set('n', '<leader>tw', ':tabclose<Return>', { desc = 'Tab close', silent = true })
  vim.keymap.set('n', '<tab>', ':tabnext<Return>', { desc = 'Tab next', silent = true })
  vim.keymap.set('n', '<s-tab>', ':tabprev<Return>', { desc = 'Tab previous', silent = true })
end

----------------------------------------
--- WINDOWS ----------------------------
----------------------------------------
-- VSCode handles window management, these are Neovim-specific
if not vim.g.vscode then
  -- Resize window with larger amounts, using winresize to resize intuitively
  local resize = function(win, amt, dir)
    return function()
      require('winresize').resize(win, amt, dir)
    end
  end
  vim.keymap.set('n', '<leader>rh', resize(0, 10, 'left'), { desc = 'Resize window left' })
  vim.keymap.set('n', '<leader>rj', resize(0, 10, 'down'), { desc = 'Resize window down' })
  vim.keymap.set('n', '<leader>rk', resize(0, 10, 'up'), { desc = 'Resize window up' })
  vim.keymap.set('n', '<leader>rl', resize(0, 10, 'right'), { desc = 'Resize window right' })
  -- Maximize / restore current split using vim-maximizer
  vim.keymap.set('n', '<leader>rm', '<cmd>MaximizerToggle<CR>', { desc = 'Maximize/minimize a split' })
end

----------------------------------------
--- AUTO-SESSION -----------------------
----------------------------------------
-- VSCode doesn't use Neovim sessions, these are Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>wr', '<cmd>SessionRestore<CR>', { desc = 'Restore session for cwd' })
  vim.keymap.set('n', '<leader>ws', '<cmd>SessionSave<CR>', { desc = 'Save session for auto session root dir' })
end

--------------------------------------------------------------------------------
--- TMUX -----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode uses workbench navigation, these conflict with VSCode Ctrl+hjkl
if not vim.g.vscode then
  vim.keymap.set('n', '<C-h>', '<cmd>TmuxNavigateLeft<CR>', { desc = 'Navigate left' })
  vim.keymap.set('n', '<C-j>', '<cmd>TmuxNavigateDown<CR>', { desc = 'Navigate down' })
  vim.keymap.set('n', '<C-k>', '<cmd>TmuxNavigateUp<CR>', { desc = 'Navigate up' })
  vim.keymap.set('n', '<C-l>', '<cmd>TmuxNavigateRight<CR>', { desc = 'Navigate right' })
  vim.keymap.set('n', '<C-\\>', '<cmd>TmuxNavigatePrevious<CR>', { desc = 'Navigate previous' })
end

--------------------------------------------------------------------------------
--- NEOVIM-TIPS -----------------------------------------------------------------------
--------------------------------------------------------------------------------
vim.keymap.set('n', '<leader>nto', '<cmd>neovimtips<cr>', { desc = 'open neovim tips' })
vim.keymap.set('n', '<leader>nte', '<cmd>neovimtipsedit<cr>', { desc = 'edit your neovim tips' })
vim.keymap.set('n', '<leader>nta', '<cmd>neovimtipsadd<cr>', { desc = 'add your neovim tip' })
vim.keymap.set('n', '<leader>nth', '<cmd>help neovim-tips<cr>', { desc = 'neovim tips help' })
vim.keymap.set('n', '<leader>ntr', '<cmd>neovimtipsrandom<cr>', { desc = 'show random tip' })
vim.keymap.set('n', '<leader>ntp', '<cmd>neovimtipspdf<cr>', { desc = 'open neovim tips pdf' })

---------------------------------------------------------------------------------
--- AI Assistant Keymaps --------------------------------------------------------
---------------------------------------------------------------------------------
-- codecompanion.nvim: Chat with Copilot (quick questions, explanations)
-- sidekick.nvim: Next Edit Suggestions (Copilot multi-line completions)
--
-- Chat keybindings:
--   <leader>ca - Chat: Ask question (works in normal/visual mode)
--   <leader>cc - Chat: Toggle chat window
--   <leader>cq - Chat: Quick actions (prompt picker)
--
-- NES (Next Edit Suggestions):
--   <Tab>      - Accept/jump to next edit suggestion
--   <leader>ne - Toggle NES on/off
--
-- Terminal workflows (for focused Claude work):
--   <leader>tt - Floaterminal (Neovim floating terminal)
--   Ctrl-g     - Tmux popup with Claude CLI

--------------------------------------------------------------------------------
--- LSP - Native Neovim 0.11+ LSP Keymaps -------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles LSP natively, these mappings are replaced by VSCode keybindings
if not vim.g.vscode then
  -- NOTE: Neovim 0.11+ provides these DEFAULT keymaps automatically:
  -- gra → vim.lsp.buf.code_action() (Normal & Visual)
  -- gri → vim.lsp.buf.implementation()
  -- grn → vim.lsp.buf.rename()
  -- grr → vim.lsp.buf.references()
  -- grt → vim.lsp.buf.type_definition()
  -- gO  → vim.lsp.buf.document_symbol()
  -- K   → vim.lsp.buf.hover() (unless keywordprg is set)
  -- <C-S> (insert) → vim.lsp.buf.signature_help()
  -- omnifunc → <C-X><C-O> for completion
  -- tagfunc → <C-]>, <C-W>], <C-W>} for go-to-definition
  -- formatexpr → gq for formatting

  -- Additional Telescope-based LSP commands using non-conflicting keys
  local tb = require('telescope.builtin')
  vim.keymap.set('n', '<leader>ld', tb.lsp_definitions, { silent = true, desc = 'Telescope: [L]SP [D]efinitions' })
  vim.keymap.set('n', '<leader>lr', tb.lsp_references, { silent = true, desc = 'Telescope: [L]SP [R]eferences' })
  vim.keymap.set('n', '<leader>li', tb.lsp_implementations, { silent = true, desc = 'Telescope: [L]SP [I]mplementations' })
  vim.keymap.set('n', '<leader>lt', tb.lsp_type_definitions, { silent = true, desc = 'Telescope: [L]SP [T]ype Definitions' })
  vim.keymap.set('n', '<leader>ds', tb.lsp_document_symbols, { silent = true, desc = 'Telescope: [D]ocument [S]ymbols' })
  vim.keymap.set('n', '<leader>ws', tb.lsp_dynamic_workspace_symbols, { silent = true, desc = 'Telescope: [W]orkspace [S]ymbols' })

  -- Declaration is not provided by default, so we add it manually
  vim.keymap.set('n', '<leader>gD', vim.lsp.buf.declaration, { silent = true, desc = '[G]oto [D]eclaration' })
end

--------------------------------------------------------------------------------
--- Oil ------------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native file navigation, Oil is Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>-', '<cmd>Oil --float<CR>', { desc = 'Open parent directory' })
  vim.keymap.set('n', 'g^', function()
    require('oil').set_columns({ 'icon', 'permissions', 'size', 'mtime' })
  end, { desc = 'Show file details' })
end

--------------------------------------------------------------------------------
--- Telescope ------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native fuzzy finding, Telescope is Neovim-specific
if not vim.g.vscode then
  local function filtered_colorschemes()
    local good_colorschemes = _G.ColorschemeManager and _G.ColorschemeManager.good_colorschemes or {}
    local display_map = _G.ColorschemeManager and _G.ColorschemeManager.display_map or {}
    local actions = require('telescope.actions')
    local action_state = require('telescope.actions.state')
    local builtin = require('telescope.builtin')
    builtin.colorscheme({
      attach_mappings = function(prompt_bufnr, map)
        actions.select_default:replace(function()
          local selection = action_state.get_selected_entry()
          actions.close(prompt_bufnr)
          vim.cmd('colorscheme ' .. selection.value)
        end)
        return true
      end,
      sorter = require('telescope.sorters').get_generic_fuzzy_sorter({ sorting_strategy = 'ascending' }),
      finder = require('telescope.finders').new_table({
        results = vim.tbl_filter(function(colorscheme)
          return vim.tbl_contains(good_colorschemes, colorscheme)
        end, vim.fn.getcompletion('', 'color')),
        entry_maker = function(cs)
          return { value = cs, display = display_map[cs] or cs, ordinal = display_map[cs] or cs }
        end,
      }),
    })
  end
  local tb = require('telescope.builtin')
  vim.keymap.set('n', '<leader>ff', tb.find_files, { desc = 'Find: Files' })
  vim.keymap.set('n', '<leader>fg', tb.live_grep, { desc = 'Find: Live grep' })
  vim.keymap.set('n', '<leader>fb', tb.buffers, { desc = 'Find: Buffers' })
  vim.keymap.set('n', '<leader>fh', tb.help_tags, { desc = 'Find: Help tags' })
  vim.keymap.set('n', '<leader>fc', tb.commands, { desc = 'Find: Commands' })
  vim.keymap.set('n', '<leader>fr', tb.registers, { desc = 'Find: Registers' })
  vim.keymap.set('n', '<leader>fq', tb.quickfix, { desc = 'Find: Quickfix' })
  vim.keymap.set('n', '<leader>fl', tb.loclist, { desc = 'Find: Location list' })
  vim.keymap.set('n', '<leader>fs', tb.lsp_document_symbols, { desc = 'Find: Document symbols' })
  vim.keymap.set('n', '<leader>fk', tb.keymaps, { desc = 'Find: Keymaps' })
  vim.keymap.set('n', '<leader>ft', tb.treesitter, { desc = 'Find: Treesitter' })
  vim.keymap.set('n', '<leader>fz', filtered_colorschemes, { desc = 'Find: Colorschemes' })
  vim.keymap.set('n', '<leader>fn', function()
    tb.find_files({
      cwd = vim.fn.stdpath('config'),
      hidden = true,
      follow = true,
    })
  end, { desc = 'Find: Neovim config files' })
end

--------------------------------------------------------------------------------
-- ZK --------------------------------------------------------------------------
--------------------------------------------------------------------------------
-- Create a new note after asking for its title.
vim.api.nvim_set_keymap('n', '<leader>zn', "<Cmd>ZkNew { title = vim.fn.input('Title: ') }<CR>", { noremap = true, silent = false })

-- Open notes.
vim.api.nvim_set_keymap('n', '<leader>zo', "<Cmd>ZkNotes { sort = { 'modified' } }<CR>", { noremap = true, silent = false })
-- Open notes associated with the selected tags.
vim.api.nvim_set_keymap('n', '<leader>zt', '<Cmd>ZkTags<CR>', { noremap = true, silent = false })

-- Search for the notes matching a given query.
vim.api.nvim_set_keymap(
  'n',
  '<leader>zf',
  "<Cmd>ZkNotes { sort = { 'modified' }, match = { vim.fn.input('Search: ') } }<CR>",
  { noremap = true, silent = false }
)
-- Search for the notes matching the current visual selection.
vim.api.nvim_set_keymap('v', '<leader>zf', ":'<,'>ZkMatch<CR>", { noremap = true, silent = false })

--------------------------------------------------------------------------------
-- Zen Mode ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native zen mode, this conflicts with VSCode zen mode keybinding
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>zz', '<cmd>ZenMode<CR>', { desc = 'Toggle Zen Mode' })
end

--------------------------------------------------------------------------------
-- LSP Format ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles formatting natively, these conflict with VSCode formatting keybindings
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>fmt', function()
    require('conform').format({ async = true, lsp_fallback = true })
  end, { desc = '[F]ormat buffer' })
  vim.keymap.set('n', '<leader>fmi', function()
    vim.lsp.buf.code_action({
      context = { only = { 'source.fixAll' }, diagnostics = {} },
      apply = true,
    })
  end, { desc = '[F]ix all linting' })
end

--------------------------------------------------------------------------------
-- Workflows ------------------------------------------------------------------
--------------------------------------------------------------------------------
-- Custom workflow system is Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>hw', function()
    require('utils.workflows').show_workflow_picker()
  end, { desc = 'Help: Workflows' })
  vim.keymap.set('n', '<leader>hk', function()
    require('utils.workflows').show_all_keymaps()
  end, { desc = 'Help: All keymaps' })
  vim.keymap.set('n', '<leader>hh', '<leader>?', { desc = 'Help: Buffer keymaps', remap = true })
end
