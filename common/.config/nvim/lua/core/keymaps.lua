-- Clear highlights on search when pressing <Esc> in normal mode
--  See `:help hlsearch`
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>', { desc = 'Clear highlights' })

-- ========================================================================== --
-- ==                             Keymaps                                 == --
-- ========================================================================== --

-- Put single character cut text in the black hole register
vim.keymap.set('n', 'x', '"_x', { desc = 'Cut >> blackhole' })

-- Select
vim.keymap.set('n', '<C-a>', 'gg<S-v>G', { desc = 'Select all' })

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
  -- Split window
  vim.keymap.set('n', '<leader><C-_>', ':split<Return>', { desc = 'Split window horizontally' })
  vim.keymap.set('n', '<leader><C_|>', ':vsplit<Return>', { desc = 'Split window vertically' })

  -- Resize window with arrows
  vim.keymap.set('n', '<C-Left>', '<C-w><', { desc = 'Resize window left' })
  vim.keymap.set('n', '<C-Right>', '<C-w>>', { desc = 'Resize window right' })
  vim.keymap.set('n', '<C-Up>', '<C-w>+', { desc = 'Resize window up' })
  vim.keymap.set('n', '<C-Down>', '<C-w>-', { desc = 'Resize window down' })
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

---------------------------------------------------------------------------------
--- CodeCompanion - Supercharged AI Assistant & Inline Search Engine ----------
---------------------------------------------------------------------------------
-- AI features only available when NVIM_AI_ENABLED=true (macOS by default)
if vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode then
  -- Core quick access - like turbocharged autocomplete
  vim.keymap.set({ 'n', 'v' }, '<C-a>', '<cmd>CodeCompanionActions<cr>', { desc = 'AI Action Palette' })
  vim.keymap.set({ 'n', 'v' }, '<leader>a', '<cmd>CodeCompanionChat Toggle<cr>', { desc = 'Toggle AI Chat' })
  vim.keymap.set('v', 'ga', '<cmd>CodeCompanionChat Add<cr>', { desc = 'Add to AI Chat' })

  -- Inline assistant - supercharged smart autocomplete
  vim.keymap.set('n', '<leader>cc', '<cmd>CodeCompanion<cr>', { desc = 'AI Inline Assistant' })
  vim.keymap.set('v', '<leader>cc', '<cmd>CodeCompanion<cr>', { desc = 'AI Process Selection' })

  -- Quick prompts - instant smart help
  vim.keymap.set({ 'n', 'v' }, '<leader>ce', '<cmd>CodeCompanion /explain<cr>', { desc = 'AI Explain' })
  vim.keymap.set({ 'n', 'v' }, '<leader>cf', '<cmd>CodeCompanion /fix<cr>', { desc = 'AI Fix' })
  vim.keymap.set({ 'n', 'v' }, '<leader>co', '<cmd>CodeCompanion /optimize<cr>', { desc = 'AI Optimize' })
  vim.keymap.set({ 'n', 'v' }, '<leader>ct', '<cmd>CodeCompanion /tests<cr>', { desc = 'AI Generate Tests' })
  vim.keymap.set({ 'n', 'v' }, '<leader>cd', '<cmd>CodeCompanion /lsp<cr>', { desc = 'AI Explain Diagnostics' })

  -- Quick web search - supercharged inline search engine
  vim.keymap.set('n', '<leader>cw', function()
    local word = vim.fn.expand('<cword>')
    vim.cmd('CodeCompanionChat @web_search query="' .. word .. '"')
  end, { desc = 'AI Web Search Word' })

  vim.keymap.set('v', '<leader>cw', function()
    -- Get visual selection
    vim.cmd('normal! "vy')
    local text = vim.fn.getreg('v')
    vim.cmd('CodeCompanionChat @web_search query="' .. text .. '"')
  end, { desc = 'AI Web Search Selection' })

  -- Quick code search
  vim.keymap.set('n', '<leader>cs', function()
    local word = vim.fn.expand('<cword>')
    vim.cmd('CodeCompanionChat @quick_search pattern="' .. word .. '"')
  end, { desc = 'AI Quick Code Search' })

  -- Repository context commands
  vim.keymap.set('n', '<leader>cr', '<cmd>CodeCompanionChat /repo<cr>', { desc = 'AI Repository Overview' })

  -- Command expansions for super quick access
  vim.cmd([[cab cc CodeCompanion]])
  vim.cmd([[cab ccc CodeCompanionChat]])
  vim.cmd([[cab cca CodeCompanionActions]])
end

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
--- Obsidian -------------------------------------------------------------------
--------------------------------------------------------------------------------
vim.keymap.set('n', '<leader>oc', "<cmd>lua require('obsidian').util.toggle_checkbox()<CR>", { desc = 'Obsidian Check Checkbox' })
vim.keymap.set('n', '<leader>ot', '<cmd>ObsidianNewFromTemplate<CR>', { desc = 'Create New Note from Template' })
vim.keymap.set('n', '<leader>oo', '<cmd>ObsidianOpen<CR>', { desc = 'Open in Obsidian App' })
vim.keymap.set('n', '<leader>ob', '<cmd>ObsidianBacklinks<CR>', { desc = 'Show ObsidianBacklinks' })
vim.keymap.set('n', '<leader>ol', '<cmd>ObsidianLinks<CR>', { desc = 'Show ObsidianLinks' })
vim.keymap.set('n', '<leader>on', '<cmd>ObsidianNew<CR>', { desc = 'Create New Note' })
vim.keymap.set('n', '<leader>os', '<cmd>ObsidianSearch<CR>', { desc = 'Search Obsidian' })
vim.keymap.set('n', '<leader>oq', '<cmd>ObsidianQuickSwitch<CR>', { desc = 'Quick Switch' })

--------------------------------------------------------------------------------
--- Oil ------------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native file navigation, Oil is Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '-', '<cmd>Oil --float<CR>', { desc = 'Open parent directory' })
  vim.keymap.set(
    'n',
    'g^',
    function() require('oil').set_columns({ 'icon', 'permissions', 'size', 'mtime' }) end,
    { desc = 'Show file details' }
  )
end

--------------------------------------------------------------------------------
--- Telescope ------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native fuzzy finding, Telescope is Neovim-specific
if not vim.g.vscode then
  local function filtered_colorschemes()
    local good_themes = {
      'terafox',
      'solarized-osaka',
      'slate',
      'rose-pine-main',
      'retrobox',
      'carbonfox',
      'OceanicNext',
      'nordic',
      'nightfox',
      'kanagawa',
      'gruvbox',
      'github_dark_default',
      'github_dark_dimmed',
      'flexoki-moon-toddler',
      'flexoki-moon-red',
      'flexoki-moon-purple',
      'flexoki-moon-green',
      'flexoki-moon-black',
    }
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
        results = vim.tbl_filter(
          function(colorscheme) return vim.tbl_contains(good_themes, colorscheme) end,
          vim.fn.getcompletion('', 'color')
        ),
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
  vim.keymap.set(
    'n',
    '<leader>fn',
    function() tb.find_files({ cwd = vim.fn.stdpath('config') }) end,
    { desc = 'Find: Neovim config files' }
  )
end

--------------------------------------------------------------------------------
-- Vim Maximizer ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles window management natively, this is Neovim-specific
if not vim.g.vscode then vim.keymap.set('n', '<leader>sm', '<cmd>MaximizerToggle<CR>', { desc = 'Maximize/minimize a split' }) end

--------------------------------------------------------------------------------
-- Zen Mode ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native zen mode, this conflicts with VSCode zen mode keybinding
if not vim.g.vscode then vim.keymap.set('n', '<leader>z', '<cmd>ZenMode<CR>', { desc = 'Toggle Zen Mode' }) end

--------------------------------------------------------------------------------
-- LSP Format ----------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles formatting natively, these conflict with VSCode formatting keybindings
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>fmt', function() vim.lsp.buf.format({ async = true }) end, { desc = '[F]ormat buffer' })
  vim.keymap.set(
    'n',
    '<leader>fmi',
    function()
      vim.lsp.buf.code_action({
        context = { only = { 'source.fixAll' }, diagnostics = {} },
        apply = true,
      })
    end,
    { desc = '[F]ix all linting' }
  )
end

--------------------------------------------------------------------------------
-- Workflows ------------------------------------------------------------------
--------------------------------------------------------------------------------
-- Custom workflow system is Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>hw', function() require('utils.workflows').show_workflow_picker() end, { desc = 'Help: Workflows' })
  vim.keymap.set('n', '<leader>hk', function() require('utils.workflows').show_all_keymaps() end, { desc = 'Help: All keymaps' })
  vim.keymap.set('n', '<leader>hh', '<leader>?', { desc = 'Help: Buffer keymaps', remap = true })
end
