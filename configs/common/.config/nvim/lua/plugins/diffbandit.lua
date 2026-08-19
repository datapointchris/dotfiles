-- Trialled alongside diffview.nvim. Both are installed on purpose: diffbandit
-- keeps each side's original formatting and draws the relationships in a
-- connector gutter instead of padding both buffers with filler lines, so the
-- two are worth using side by side before picking one.

-- `vim.ui.input` with completion='file' rather than a picker: the second path is
-- usually typed, not browsed, and dressing.nvim already renders the prompt.
local function ask(prompt, default, on_answer)
  vim.ui.input({ prompt = prompt, default = default, completion = 'file' }, function(answer)
    if answer and answer ~= '' then on_answer(vim.fn.fnamemodify(vim.fn.expand(answer), ':p')) end
  end)
end

local function diff_two_files()
  ask('Left file: ', vim.fn.expand('%:p'), function(left)
    ask(
      'Right file: ',
      vim.fn.fnamemodify(left, ':h') .. '/',
      function(right) vim.cmd(('DiffBandit %s %s'):format(vim.fn.fnameescape(left), vim.fn.fnameescape(right))) end
    )
  end)
end

local function diff_against_current()
  local current = vim.fn.expand('%:p')
  if current == '' then
    vim.notify('No file in this buffer', vim.log.levels.WARN)
    return
  end
  ask(
    'Diff against: ',
    vim.fn.expand('%:p:h') .. '/',
    function(other) vim.cmd(('DiffBandit %s %s'):format(vim.fn.fnameescape(current), vim.fn.fnameescape(other))) end
  )
end

local function diff_two_folders()
  ask('Left folder: ', vim.fn.getcwd() .. '/', function(left)
    ask(
      'Right folder: ',
      vim.fn.fnamemodify(left:gsub('/$', ''), ':h') .. '/',
      function(right) vim.cmd(('DiffBanditFolderDiff %s %s'):format(vim.fn.fnameescape(left), vim.fn.fnameescape(right))) end
    )
  end)
end

return {
  'CoreyKaylor/diffbandit.nvim',
  opts = {},
  cmd = {
    'DiffBandit',
    'DiffBanditBuffers',
    'DiffBanditFolderDiff',
    'DiffBanditGit',
    'DiffBanditGitCurrent',
    'DiffBanditGitLog',
    'DiffBanditGitCommit',
    'DiffBanditGitCompare',
    'DiffBanditGitCheckout',
    'DiffBanditGitMenu',
    'DiffBanditCommitPanel',
    'DiffBanditMerge',
  },
  keys = {
    -- Two arbitrary files, which is the one case neither diffview nor any
    -- git-scoped mapping can serve: DiffviewOpen takes git revisions, so it
    -- cannot compare an untracked file against anything.
    { '<leader>gB2', diff_two_files, desc = 'DiffBandit: diff two files' },
    { '<leader>gBo', diff_against_current, desc = 'DiffBandit: diff this file against another' },
    { '<leader>gBF', diff_two_folders, desc = 'DiffBandit: diff two folders' },

    { '<leader>gBd', '<cmd>DiffBanditGit<cr>', desc = 'DiffBandit: changed files' },
    { '<leader>gBf', '<cmd>DiffBanditGitCurrent<cr>', desc = 'DiffBandit: current file diff' },
    { '<leader>gBl', '<cmd>DiffBanditGitLog<cr>', desc = 'DiffBandit: commit log' },
    { '<leader>gBc', '<cmd>DiffBanditCommitPanel<cr>', desc = 'DiffBandit: commit panel' },
    { '<leader>gBm', '<cmd>DiffBanditGitMenu<cr>', desc = 'DiffBandit: git menu' },
  },
}
