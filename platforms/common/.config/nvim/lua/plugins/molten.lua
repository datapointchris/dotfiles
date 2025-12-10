-- Molten-nvim: Jupyter kernel integration for Neovim
-- Enables interactive notebook-style development with Jupyter kernels
-- Perfect for AWS Glue local development with PySpark

return {
  {
    'benlubas/molten-nvim',
    version = '^1.0.0',
    cond = not vim.g.vscode,
    dependencies = { '3rd/image.nvim' },
    build = ':UpdateRemotePlugins',
    init = function()
      -- Configuration
      vim.g.molten_auto_open_output = true
      vim.g.molten_output_win_max_height = 20
      vim.g.molten_wrap_output = true
      vim.g.molten_virt_text_output = true
      vim.g.molten_virt_lines_off_by_1 = true
      vim.g.molten_use_border_highlights = true
    end,
    config = function()
      -- Keybindings for Jupyter-like workflow
      vim.keymap.set('n', '<leader>mi', ':MoltenInit ', { desc = 'Molten: Initialize kernel' })
      vim.keymap.set('n', '<leader>mp', ':MoltenInit python3<CR>', { desc = 'Molten: Initialize Python kernel' })
      vim.keymap.set('n', '<leader>me', ':MoltenEvaluateOperator<CR>', { desc = 'Molten: Evaluate operator' })
      vim.keymap.set('n', '<leader>ml', ':MoltenEvaluateLine<CR>', { desc = 'Molten: Evaluate line' })
      vim.keymap.set('v', '<leader>mv', ':<C-u>MoltenEvaluateVisual<CR>gv', { desc = 'Molten: Evaluate visual' })
      vim.keymap.set('n', '<leader>mc', ':MoltenReevaluateCell<CR>', { desc = 'Molten: Re-evaluate cell' })
      vim.keymap.set('n', '<leader>md', ':MoltenDelete<CR>', { desc = 'Molten: Delete cell' })
      vim.keymap.set('n', '<leader>mo', ':MoltenShowOutput<CR>', { desc = 'Molten: Show output' })
      vim.keymap.set('n', '<leader>mh', ':MoltenHideOutput<CR>', { desc = 'Molten: Hide output' })
      vim.keymap.set('n', '<leader>mq', ':MoltenDeinit<CR>', { desc = 'Molten: Stop kernel' })

      -- Enter output window (useful for scrolling through long outputs)
      vim.keymap.set('n', '<leader>me', ':MoltenEnterOutput<CR>', { desc = 'Molten: Enter output window' })

      -- Import/export notebook outputs
      vim.keymap.set('n', '<leader>mx', ':MoltenExportOutput<CR>', { desc = 'Molten: Export output' })
      vim.keymap.set('n', '<leader>mI', ':MoltenImportOutput<CR>', { desc = 'Molten: Import output' })
    end,
  },

  -- Image rendering support (optional but nice for data visualization)
  {
    '3rd/image.nvim',
    cond = not vim.g.vscode and #vim.api.nvim_list_uis() > 0,
    opts = {
      backend = 'kitty', -- or 'ueberzug' if not using Kitty terminal
      integrations = {
        markdown = {
          enabled = true,
          clear_in_insert_mode = false,
          download_remote_images = true,
          only_render_image_at_cursor = false,
        },
        neorg = {
          enabled = false,
        },
      },
      max_width = 100,
      max_height = 12,
      max_width_window_percentage = nil,
      max_height_window_percentage = 50,
      window_overlap_clear_enabled = false,
      window_overlap_clear_ft_ignore = { 'cmp_menu', 'cmp_docs', '' },
      editor_only_render_when_focused = false,
      tmux_show_only_in_active_window = false,
      hijack_file_patterns = { '*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp' },
    },
  },
}
