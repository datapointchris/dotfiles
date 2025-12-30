-- codecompanion.nvim - Chat with Copilot
-- Purpose: Quick questions, explanations, code examples (NO forced code changes)
--
-- Keybindings:
--   <leader>ca - Inline chat (ask question, get answer)
--   <leader>cc - Toggle chat window
--   <leader>cq - Quick chat (prompt picker)

return {
  {
    'olimorris/codecompanion.nvim',
    cond = not vim.g.vscode, -- VS Code has GitHub Copilot Chat
    enabled = true,
    dependencies = {
      'nvim-lua/plenary.nvim',
      'nvim-treesitter/nvim-treesitter',
      'zbirenbaum/copilot.lua', -- Use Copilot for chat
    },
    opts = {
      strategies = {
        chat = { adapter = 'copilot' },
        inline = { adapter = 'copilot' },
      },
      display = {
        chat = {
          window = {
            layout = 'vertical',
            position = 'right',
            width = 0.4,
            border = 'rounded',
          },
          show_settings = false,
        },
      },
    },
    keys = {
      { '<leader>ca', '<cmd>CodeCompanionChat<cr>', mode = { 'n', 'v' }, desc = 'Chat: Ask (inline)' },
      { '<leader>cc', '<cmd>CodeCompanionChat Toggle<cr>', mode = 'n', desc = 'Chat: Toggle window' },
      { '<leader>cq', '<cmd>CodeCompanionActions<cr>', mode = { 'n', 'v' }, desc = 'Chat: Quick actions' },
    },
  },
}
