-- Clear highlights on search when pressing <Esc> in normal mode
--  See `:help hlsearch`
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>', { desc = 'Clear highlights' })

-- Put single character cut text in the black hole register
vim.keymap.set('n', 'x', '"_x', { desc = 'Cut >> blackhole' })

-- Select all
vim.keymap.set('n', '<C-a>', 'gg<S-v>G', { desc = 'Select all' })

-- Reload neovim config or execute lua
vim.keymap.set('n', '<leader>rr', '<cmd>source ~/.config/nvim/init.lua<cr>', { desc = 'Reload: source init.lua' })
vim.keymap.set('n', '<leader>rx', ':.lua<cr>', { desc = 'Reload: run current line as lua' })
vim.keymap.set('v', '<leader>rx', ':lua<cr>', { desc = 'Reload: run selection as lua' })

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

-- Paste text from the system clipboard
vim.keymap.set({ 'n', 'v' }, '<leader>p', [["+p]], { desc = 'Paste from system clipboard' })

-- Navigate the quickfix list (vim-unimpaired convention)
vim.keymap.set('n', ']q', '<cmd>cnext<CR>zz', { desc = 'Quickfix: next' })
vim.keymap.set('n', '[q', '<cmd>cprev<CR>zz', { desc = 'Quickfix: previous' })

-- Navigate the location list (vim-unimpaired convention)
vim.keymap.set('n', ']l', '<cmd>lnext<CR>zz', { desc = 'Loclist: next' })
vim.keymap.set('n', '[l', '<cmd>lprev<CR>zz', { desc = 'Loclist: previous' })

----------------------------------------
--- QUITTING -------------------------------
----------------------------------------
vim.keymap.set('n', '<leader>qq', ':q<CR>', { noremap = true, silent = true, desc = 'Quit: Current buffer' })
vim.keymap.set('n', '<leader>qa', ':qa<CR>', { noremap = true, silent = true, desc = 'Quit: All buffers' })
vim.keymap.set('n', '<leader>qs', ':wq<CR>', { noremap = true, silent = true, desc = 'Quit: Save and quit' })
vim.keymap.set('n', '<leader>qx', ':wqa<CR>', { noremap = true, silent = true, desc = 'Quit: Save all and quit' })
vim.keymap.set('n', '<leader>qQ', ':q!<CR>', { noremap = true, silent = true, desc = 'Quit: Force quit (no save)' })
vim.keymap.set('n', '<leader>qA', ':qa!<CR>', { noremap = true, silent = true, desc = 'Quit: Force quit all (no save)' })

----------------------------------------
--- TABS -------------------------------
----------------------------------------
-- Tab next/previous use native gt/gT. <Tab>/<S-Tab> are deliberately NOT mapped:
-- terminals send the same byte for <Tab> and <C-i>, so mapping <Tab> would shadow
-- <C-i> (jump forward in the jumplist, the partner to <C-o>).
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>te', ':tabedit', { desc = 'Tab edit' })
  vim.keymap.set('n', '<leader>tw', ':tabclose<Return>', { desc = 'Tab close', silent = true })
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
  vim.keymap.set('n', '<leader>wh', resize(0, 10, 'left'), { desc = 'Window resize left' })
  vim.keymap.set('n', '<leader>wj', resize(0, 10, 'down'), { desc = 'Window resize down' })
  vim.keymap.set('n', '<leader>wk', resize(0, 10, 'up'), { desc = 'Window resize up' })
  vim.keymap.set('n', '<leader>wl', resize(0, 10, 'right'), { desc = 'Window resize right' })
  -- Same resize action via Ctrl+Alt+arrow chord — pairs with tmux's matching binding
  -- so resize works identically across pane and split boundaries.
  vim.keymap.set('n', '<C-M-Left>', resize(0, 10, 'left'), { desc = 'Window resize left' })
  vim.keymap.set('n', '<C-M-Down>', resize(0, 10, 'down'), { desc = 'Window resize down' })
  vim.keymap.set('n', '<C-M-Up>', resize(0, 10, 'up'), { desc = 'Window resize up' })
  vim.keymap.set('n', '<C-M-Right>', resize(0, 10, 'right'), { desc = 'Window resize right' })
  -- Maximize / restore current split using vim-maximizer
  vim.keymap.set('n', '<leader>wm', '<cmd>MaximizerToggle<CR>', { desc = 'Window maximize/minimize' })
end

----------------------------------------
--- AUTO-SESSION -----------------------
----------------------------------------
-- VSCode doesn't use Neovim sessions, these are Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>wr', '<cmd>SessionRestore<CR>', { desc = 'Restore session for cwd' })
end

--------------------------------------------------------------------------------
-- Tmux pane navigation (<C-arrow>, <C-\>) is defined as lazy `keys` in
-- lua/plugins/vim-tmux-navigator.lua so it loads the plugin on first use.

--------------------------------------------------------------------------------
--- LSP ------------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles LSP natively, these mappings are replaced by VSCode keybindings
if not vim.g.vscode then
  -- Default LSP keymaps (gra, gri, grn, grr, grt, gO, K, C-S, etc.) are
  -- provided by Neovim. K is explicitly mapped in autocmds.lua LspAttach to
  -- override keywordprg for filetypes like Python that set it to pydoc.

  -- Telescope-based LSP commands using non-conflicting keys
  local tb = require('telescope.builtin')
  vim.keymap.set('n', '<leader>ld', tb.lsp_definitions, { silent = true, desc = 'Telescope: [L]SP [D]efinitions' })
  vim.keymap.set('n', '<leader>lr', tb.lsp_references, { silent = true, desc = 'Telescope: [L]SP [R]eferences' })
  vim.keymap.set('n', '<leader>li', tb.lsp_implementations, { silent = true, desc = 'Telescope: [L]SP [I]mplementations' })
  vim.keymap.set('n', '<leader>lt', tb.lsp_type_definitions, { silent = true, desc = 'Telescope: [L]SP [T]ype Definitions' })
  vim.keymap.set('n', '<leader>ls', tb.lsp_document_symbols, { silent = true, desc = 'Telescope: [L]SP document [S]ymbols' })
  vim.keymap.set('n', '<leader>lS', tb.lsp_dynamic_workspace_symbols, { silent = true, desc = 'Telescope: [L]SP workspace [S]ymbols' })

  -- Declaration is not provided by default, so we add it manually
  vim.keymap.set('n', '<leader>lD', vim.lsp.buf.declaration, { silent = true, desc = '[L]SP [D]eclaration' })
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
        -- Use the manager's curated list directly rather than getcompletion():
        -- theme plugins are lazy-loaded, so unloaded ones aren't on the
        -- runtimepath yet and wouldn't appear. Selecting one triggers
        -- lazy.nvim's ColorSchemePre load.
        results = good_colorschemes,
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
vim.api.nvim_set_keymap(
  'n',
  '<leader>zn',
  "<Cmd>ZkNew { title = vim.fn.input('Title: ') }<CR>",
  { noremap = true, silent = false, desc = 'Notes: new note' }
)

-- Open notes.
vim.api.nvim_set_keymap(
  'n',
  '<leader>zo',
  "<Cmd>ZkNotes { sort = { 'modified' } }<CR>",
  { noremap = true, silent = false, desc = 'Notes: open notes' }
)
-- Open notes associated with the selected tags.
vim.api.nvim_set_keymap('n', '<leader>zt', '<Cmd>ZkTags<CR>', { noremap = true, silent = false, desc = 'Notes: open by tag' })

-- Search for the notes matching a given query.
vim.api.nvim_set_keymap(
  'n',
  '<leader>zf',
  "<Cmd>ZkNotes { sort = { 'modified' }, match = { vim.fn.input('Search: ') } }<CR>",
  { noremap = true, silent = false, desc = 'Notes: search by query' }
)
-- Search for the notes matching the current visual selection.
vim.api.nvim_set_keymap('v', '<leader>zf', ":'<,'>ZkMatch<CR>", { noremap = true, silent = false, desc = 'Notes: search by selection' })

--------------------------------------------------------------------------------
-- Zen Mode ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native zen mode, this conflicts with VSCode zen mode keybinding
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>zz', '<cmd>ZenMode<CR>', { desc = 'Toggle Zen Mode' })
end

--------------------------------------------------------------------------------
-- Code (format, fix, rename) --------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles these natively; Neovim-only here
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>cf', function()
    require('conform').format({ async = true, lsp_fallback = true })
  end, { desc = 'Code: [f]ormat buffer' })
  vim.keymap.set('n', '<leader>ci', function()
    vim.lsp.buf.code_action({
      context = { only = { 'source.fixAll' }, diagnostics = {} },
      apply = true,
    })
  end, { desc = 'Code: fix all l[i]nting' })
  -- inc-rename: live-preview LSP rename, prefilled with the word under cursor
  vim.keymap.set('n', '<leader>cr', function()
    return ':IncRename ' .. vim.fn.expand('<cword>')
  end, { expr = true, desc = 'Code: [r]ename symbol' })
end
