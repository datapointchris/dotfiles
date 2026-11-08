return {
  'rmagatti/auto-session',
  lazy = false,
  -- prs starts nvim in the repo's checkout to show a pull request's diff, with
  -- PRS_DIFF_DOCUMENT set. Saving there at exit would replace the repo's session
  -- with the diff's buffers, which are gone once nvim exits.
  cond = function()
    return not vim.env.PRS_DIFF_DOCUMENT
  end,
  opts = {
    suppressed_dirs = { '~/', '~/Downloads', '~/Documents', '~/Desktop/', '/' },
  },
}
