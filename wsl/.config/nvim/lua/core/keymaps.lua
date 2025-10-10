-- Clear highlights on search when pressing <Esc> in normal mode
--  See `:help hlsearch`
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>', { desc = 'Clear highlights' })

-- Unbind default bindings for arrow keys, trust me this is for your own good
vim.keymap.set('v', '<up>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('v', '<down>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('v', '<left>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('v', '<right>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('i', '<up>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('i', '<down>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('i', '<left>', '<nop>', { desc = 'Unbind for your benefit' })
vim.keymap.set('i', '<right>', '<nop>', { desc = 'Unbind for your benefit' })

-- Put single character cut text in the black hole register
vim.keymap.set('n', 'x', '"_x', { desc = 'Cut >> blackhole' })

-- Increment/decrement numbers under the cursor
vim.keymap.set('n', '+', '<C-a>', { desc = 'Increment number under cursor' })
vim.keymap.set('n', '-', '<C-x>', { desc = 'Decrement number under cursor' })

-- Select all
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
vim.keymap.set('n', '<leader>qq', ':q<CR>', { noremap = true, silent = true, desc = 'Quit' })
vim.keymap.set('n', '<leader>qa', ':qa<CR>', { noremap = true, silent = true, desc = 'Quit all' })
vim.keymap.set('n', '<leader>qs', ':wq<CR>', { noremap = true, silent = true, desc = 'Save and Quit' })
vim.keymap.set('n', '<leader>qx', ':wqa<CR>', { noremap = true, silent = true, desc = 'Save All and Quit' })
vim.keymap.set('n', '<leader>qQ', ':q!<CR>', { noremap = true, silent = true, desc = 'Quit without saving' })
vim.keymap.set('n', '<leader>QQ', ':qa!<CR>', { noremap = true, silent = true, desc = 'Quit All without saving' })

----------------------------------------
--- TABS -------------------------------
----------------------------------------
-- VSCode handles tabs natively, these conflict with VSCode tab navigation
if not vim.g.vscode then
  vim.keymap.set('n', 'te', ':tabedit', { desc = 'Tab edit' })
  vim.keymap.set('n', '<tab>', ':tabnext<Return>', { desc = 'Tab next', silent = true })
  vim.keymap.set('n', '<s-tab>', ':tabprev<Return>', { desc = 'Tab previous', silent = true })
  vim.keymap.set('n', 'tw', ':tabclose<Return>', { desc = 'Tab close', silent = true })
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

--------------------------------------------------------------------------------
--- NeoTree --------------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode has native file explorer, NeoTree is Neovim-specific
if not vim.g.vscode then
  vim.keymap.set('n', '<leader>tt', ':Neotree filesystem toggle right<CR>', { desc = 'Toggle file tree' })
  vim.keymap.set('n', '<leader>tf', ':Neotree focus right<CR>', { desc = 'Toggle file tree' })
  vim.keymap.set('n', '<leader>tg', ':Neotree float git_status<CR>', { desc = 'Toggle file tree' })
end

--------------------------------------------------------------------------------
--- nvim-lspconfig -------------------------------------------------------------
--------------------------------------------------------------------------------
-- VSCode handles LSP natively, these mappings are replaced by VSCode keybindings
if not vim.g.vscode then
  local tb = require('telescope.builtin')
  vim.keymap.set('n', 'gd', tb.lsp_definitions, { silent = true, desc = '[G]oto [D]efinition' })
  vim.keymap.set('n', 'gr', tb.lsp_references, { silent = true, desc = '[G]oto [R]eferences' })
  vim.keymap.set('n', 'gI', tb.lsp_implementations, { silent = true, desc = '[G]oto [I]mplementation' })
  vim.keymap.set('n', '<leader>D', tb.lsp_type_definitions, { silent = true, desc = 'Type [D]efinition' })
  vim.keymap.set('n', '<leader>ds', tb.lsp_document_symbols, { silent = true, desc = '[D]ocument [S]ymbols' })
  vim.keymap.set('n', '<leader>ws', tb.lsp_dynamic_workspace_symbols, { silent = true, desc = '[W]orkspace [S]ymbols' })
  vim.keymap.set('n', '<leader>rn', vim.lsp.buf.rename, { silent = true, desc = '[R]e[n]ame' })
  vim.keymap.set('n', 'gD', vim.lsp.buf.declaration, { silent = true, desc = '[G]oto [D]eclaration' })
  vim.keymap.set({ 'n', 'x' }, '<leader>ca', vim.lsp.buf.code_action, { silent = true, desc = '[C]ode [A]ction' })
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
    local bad_themes = {
      'blue',
      'darkblue',
      'dawnfox',
      'dayfox',
      'delek',
      'desert',
      'elflord',
      'evening',
      'github_dark_high_contrast',
      'github_light_colorblind',
      'github_light_default',
      'github_light_high_contrast',
      'github_light_tritanopia',
      'github_light',
      'habamax',
      'industry',
      'kanagawa-lotus',
      'koehler',
      'lunaperche',
      'minicyan',
      'minischeme',
      'morning',
      'murphy',
      'OceanicNextLight',
      'pablo',
      'peachpuff',
      'quiet',
      'randomhue',
      'ron',
      'rose-pine-dawn',
      'rose-pine',
      'shine',
      'solarized-osaka-day',
      'solarized-osaka-storm',
      'solarized-osaka-night',
      'solarized-osaka-moon',
      'sorbet',
      'torte',
      'vim',
      'wildcharm',
      'zaibatsu',
      'zellner',
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
          function(colorscheme) return not vim.tbl_contains(bad_themes, colorscheme) end,
          vim.fn.getcompletion('', 'color')
        ),
      }),
    })
  end
  local tb = require('telescope.builtin')
  vim.keymap.set('n', '<leader>ff', tb.find_files, { desc = 'Find files' })
  vim.keymap.set('n', '<leader>fg', tb.live_grep, { desc = 'Live grep' })
  vim.keymap.set('n', '<leader>fb', tb.buffers, { desc = 'Buffers' })
  vim.keymap.set('n', '<leader>fh', tb.help_tags, { desc = 'Help tags' })
  vim.keymap.set('n', '<leader>fc', tb.commands, { desc = 'Commands' })
  vim.keymap.set('n', '<leader>fr', tb.registers, { desc = 'Registers' })
  vim.keymap.set('n', '<leader>fq', tb.quickfix, { desc = 'Quickfix' })
  vim.keymap.set('n', '<leader>fl', tb.loclist, { desc = 'Location list' })
  vim.keymap.set('n', '<leader>fs', tb.lsp_document_symbols, { desc = 'LSP document symbols' })
  vim.keymap.set('n', '<leader>fk', tb.keymaps, { desc = 'Keymaps' })
  vim.keymap.set('n', '<leader>ft', tb.treesitter, { desc = 'Treesitter' })
  vim.keymap.set('n', '<leader>fz', filtered_colorschemes, { desc = 'Color scheme picker' })
  vim.keymap.set(
    'n',
    '<leader>fn',
    function() tb.find_files({ cwd = vim.fn.stdpath('config') }) end,
    { desc = 'Search neovim config files' }
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
  vim.keymap.set('n', '<leader>hw', function() require('utils.workflows').show_workflow_picker() end, { desc = 'Help: Show workflows' })
  vim.keymap.set('n', '<leader>hk', function() require('utils.workflows').show_all_keymaps() end, { desc = 'Help: Show all keymaps' })
  vim.keymap.set('n', '<leader>hh', '<leader>?', { desc = 'Help: Show buffer keymaps (which-key)', remap = true })
end
