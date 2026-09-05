-- Jupyter kernel execution inside a buffer: out-of-order cells, and each cell's
-- own output attached to the lines that produced it. That last part is the whole
-- reason this exists — a REPL in a terminal split gives linear execution and one
-- shared scrollback, so re-running an earlier cell puts its result at the bottom
-- with nothing tying it back.
--
-- Text output only. `image.nvim` is deliberately absent: it needs the ImageMagick
-- LuaRock and a terminal speaking the kitty or sixel protocol, neither of which
-- exists under WSL, and `molten_virt_text_output` renders results as virtual text
-- with no graphics stack at all.
--
-- `MoltenInit` takes a URL as well as a kernel name — anything starting `http://`
-- or `https://` is handed to `JupyterAPIManager` instead of a local kernel. So a
-- kernel running in a container is reachable by publishing its Jupyter server
-- port and passing the URL with its token:
--
--     :MoltenInit http://localhost:8888?token=<token>
--
-- The kernel is then whatever the container has, which is how a Glue image gives
-- a real `GlueContext` with no JVM on this machine.
--
-- Needs `pynvim` and `jupyter_client` in whatever `vim.g.python3_host_prog` names,
-- plus `requests` and `websocket` for the URL form. core/options.lua points that
-- at the jupyterlab tool venv, which carries all four.

--- Evaluate the `# %%` cell the cursor is inside.
---
--- `MoltenReevaluateCell` re-runs an already-evaluated region, so it cannot start
--- one. This finds the cell bounds by the marker and evaluates that range, which
--- is what makes a fresh `# %%` block runnable.
---
--- `MoltenEvaluateRange` is registered as a function rather than a command, so it
--- is called through `vim.fn` and not `vim.cmd`.
---@return nil
local function evaluate_percent_cell()
  local marker = '^%s*# %%%%'
  local cursor = vim.api.nvim_win_get_cursor(0)[1]
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)

  local first = 1
  for index = cursor, 1, -1 do
    if lines[index] and lines[index]:match(marker) then
      first = index
      break
    end
  end

  local last = #lines
  for index = cursor + 1, #lines do
    if lines[index]:match(marker) then
      last = index - 1
      break
    end
  end

  vim.fn.MoltenEvaluateRange(first, last)
end

return {
  'benlubas/molten-nvim',
  version = '^1.0.0',
  build = ':UpdateRemotePlugins',
  ft = { 'python', 'markdown', 'quarto' },
  init = function()
    -- Virtual text is the output surface, so the floating window must not also
    -- open on every evaluation — two renderings of one result, one of them
    -- covering the buffer.
    vim.g.molten_virt_text_output = true
    vim.g.molten_auto_open_output = false

    vim.g.molten_image_provider = 'none'
    vim.g.molten_output_win_max_height = 20
    vim.g.molten_wrap_output = true
    vim.g.molten_use_border_highlights = true
    -- Without this the virtual lines sit one row above the cell they belong to.
    vim.g.molten_virt_lines_off_by_1 = true
  end,
  keys = {
    { '<leader>mp', '<cmd>MoltenInit python3<cr>', desc = 'Molten: start the python3 kernel' },
    { '<leader>mi', ':MoltenInit ', desc = 'Molten: start a named kernel' },
    { '<leader>mr', ':MoltenInit http://localhost:8888?token=', desc = 'Molten: attach to a Jupyter server' },
    { '<leader>mq', '<cmd>MoltenDeinit<cr>', desc = 'Molten: stop the kernel' },
    { '<leader>mR', '<cmd>MoltenRestart<cr>', desc = 'Molten: restart the kernel' },

    { '<leader>mm', evaluate_percent_cell, desc = 'Molten: evaluate the # %% cell' },
    { '<leader>ml', '<cmd>MoltenEvaluateLine<cr>', desc = 'Molten: evaluate line' },
    { '<leader>me', '<cmd>MoltenEvaluateOperator<cr>', desc = 'Molten: evaluate operator' },
    { '<leader>mv', ':<C-u>MoltenEvaluateVisual<cr>gv', mode = 'v', desc = 'Molten: evaluate selection' },
    { '<leader>mc', '<cmd>MoltenReevaluateCell<cr>', desc = 'Molten: re-evaluate cell' },
    -- A Spark action can run for minutes, and the alternative to interrupting is
    -- restarting the kernel and losing the session.
    { '<leader>mk', '<cmd>MoltenInterrupt<cr>', desc = 'Molten: interrupt execution' },

    -- `mw` rather than a second `me`. Both were bound to `me` before, so the
    -- operator mapping never fired.
    { '<leader>mw', '<cmd>MoltenEnterOutput<cr>', desc = 'Molten: enter output window' },
    { '<leader>mo', '<cmd>MoltenShowOutput<cr>', desc = 'Molten: show output' },
    { '<leader>mh', '<cmd>MoltenHideOutput<cr>', desc = 'Molten: hide output' },
    { '<leader>md', '<cmd>MoltenDelete<cr>', desc = 'Molten: delete cell' },
    { '<leader>mI', '<cmd>MoltenInfo<cr>', desc = 'Molten: kernel info' },

    { ']m', '<cmd>MoltenNext<cr>', desc = 'Molten: next cell' },
    { '[m', '<cmd>MoltenPrev<cr>', desc = 'Molten: previous cell' },
  },
}
