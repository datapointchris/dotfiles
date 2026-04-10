return {
  'nvim-treesitter/nvim-treesitter-textobjects',
  branch = 'main',
  lazy = true,
  config = function()
    require('nvim-treesitter-textobjects').setup({
      select = { lookahead = true },
      move = { set_jumps = true },
    })

    -- Select keymaps (visual + operator-pending)
    local select_maps = {
      ['a='] = { query = '@assignment.outer', desc = 'Select outer part of an assignment' },
      ['i='] = { query = '@assignment.inner', desc = 'Select inner part of an assignment' },
      ['a:'] = { query = '@property.outer', desc = 'Select outer part of an object property' },
      ['i:'] = { query = '@property.inner', desc = 'Select inner part of an object property' },
      ['aa'] = { query = '@parameter.outer', desc = 'Select outer part of a parameter/argument' },
      ['ia'] = { query = '@parameter.inner', desc = 'Select inner part of a parameter/argument' },
      ['ai'] = { query = '@conditional.outer', desc = 'Select outer part of a conditional' },
      ['ii'] = { query = '@conditional.inner', desc = 'Select inner part of a conditional' },
      ['al'] = { query = '@loop.outer', desc = 'Select outer part of a loop' },
      ['il'] = { query = '@loop.inner', desc = 'Select inner part of a loop' },
      ['af'] = { query = '@function.outer', desc = 'Select outer part of a function call' },
      ['if'] = { query = '@function.inner', desc = 'Select inner part of a function call' },
      ['ac'] = { query = '@class.outer', desc = 'Select outer part of a class' },
      ['ic'] = { query = '@class.inner', desc = 'Select inner part of a class' },
    }

    local ts_select = require('nvim-treesitter-textobjects.select')
    for lhs, map in pairs(select_maps) do
      vim.keymap.set({ 'x', 'o' }, lhs, function()
        ts_select.select_textobject(map.query)
      end, { desc = map.desc })
    end

    -- Swap keymaps (normal mode)
    local ts_swap = require('nvim-treesitter-textobjects.swap')
    local swap_next_maps = {
      ['<leader>na'] = { query = '@parameter.inner', desc = 'Swap parameter/argument with next' },
      ['<leader>n:'] = { query = '@property.outer', desc = 'Swap object property with next' },
      ['<leader>nm'] = { query = '@function.outer', desc = 'Swap function with next' },
    }
    local swap_prev_maps = {
      ['<leader>pa'] = { query = '@parameter.inner', desc = 'Swap parameter/argument with prev' },
      ['<leader>p:'] = { query = '@property.outer', desc = 'Swap object property with prev' },
      ['<leader>pm'] = { query = '@function.outer', desc = 'Swap function with previous' },
    }

    for lhs, map in pairs(swap_next_maps) do
      vim.keymap.set('n', lhs, function()
        ts_swap.swap_next(map.query)
      end, { desc = map.desc })
    end
    for lhs, map in pairs(swap_prev_maps) do
      vim.keymap.set('n', lhs, function()
        ts_swap.swap_previous(map.query)
      end, { desc = map.desc })
    end

    -- Move keymaps (normal + visual + operator-pending)
    local ts_move = require('nvim-treesitter-textobjects.move')
    local move_maps = {
      -- goto_next_start
      { ']f', 'goto_next_start', '@call.outer', nil, 'Next function call start' },
      { ']m', 'goto_next_start', '@function.outer', nil, 'Next method/function def start' },
      { ']c', 'goto_next_start', '@class.outer', nil, 'Next class start' },
      { ']i', 'goto_next_start', '@conditional.outer', nil, 'Next conditional start' },
      { ']l', 'goto_next_start', '@loop.outer', nil, 'Next loop start' },
      { ']s', 'goto_next_start', '@scope', 'locals', 'Next scope' },
      { ']z', 'goto_next_start', '@fold', 'folds', 'Next fold' },
      -- goto_next_end
      { ']F', 'goto_next_end', '@call.outer', nil, 'Next function call end' },
      { ']M', 'goto_next_end', '@function.outer', nil, 'Next method/function def end' },
      { ']C', 'goto_next_end', '@class.outer', nil, 'Next class end' },
      { ']I', 'goto_next_end', '@conditional.outer', nil, 'Next conditional end' },
      { ']L', 'goto_next_end', '@loop.outer', nil, 'Next loop end' },
      -- goto_previous_start
      { '[f', 'goto_previous_start', '@call.outer', nil, 'Prev function call start' },
      { '[m', 'goto_previous_start', '@function.outer', nil, 'Prev method/function def start' },
      { '[c', 'goto_previous_start', '@class.outer', nil, 'Prev class start' },
      { '[i', 'goto_previous_start', '@conditional.outer', nil, 'Prev conditional start' },
      { '[l', 'goto_previous_start', '@loop.outer', nil, 'Prev loop start' },
      -- goto_previous_end
      { '[F', 'goto_previous_end', '@call.outer', nil, 'Prev function call end' },
      { '[M', 'goto_previous_end', '@function.outer', nil, 'Prev method/function def end' },
      { '[C', 'goto_previous_end', '@class.outer', nil, 'Prev class end' },
      { '[I', 'goto_previous_end', '@conditional.outer', nil, 'Prev conditional end' },
      { '[L', 'goto_previous_end', '@loop.outer', nil, 'Prev loop end' },
    }

    for _, map in ipairs(move_maps) do
      local lhs, fn_name, query, query_group, desc = map[1], map[2], map[3], map[4], map[5]
      vim.keymap.set({ 'n', 'x', 'o' }, lhs, function()
        ts_move[fn_name](query, query_group)
      end, { desc = desc })
    end

    -- Repeatable movements with ; and ,
    local ts_repeat_move = require('nvim-treesitter-textobjects.repeatable_move')

    vim.keymap.set({ 'n', 'x', 'o' }, ';', ts_repeat_move.repeat_last_move_next)
    vim.keymap.set({ 'n', 'x', 'o' }, ',', ts_repeat_move.repeat_last_move_previous)

    -- Make builtin f, F, t, T also repeatable with ; and ,
    vim.keymap.set({ 'n', 'x', 'o' }, 'f', ts_repeat_move.builtin_f_expr, { expr = true })
    vim.keymap.set({ 'n', 'x', 'o' }, 'F', ts_repeat_move.builtin_F_expr, { expr = true })
    vim.keymap.set({ 'n', 'x', 'o' }, 't', ts_repeat_move.builtin_t_expr, { expr = true })
    vim.keymap.set({ 'n', 'x', 'o' }, 'T', ts_repeat_move.builtin_T_expr, { expr = true })
  end,
}
