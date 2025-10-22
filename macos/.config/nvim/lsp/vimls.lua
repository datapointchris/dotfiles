-- Vim Script Language Server
return {
  cmd = { 'vim-language-server', '--stdio' },
  filetypes = { 'vim' },
  root_markers = { '.vimrc', 'init.vim', '.git' },
  settings = {
    vim = {
      indexes = {
        count = 3,
        gap = 100,
        projectRootPatterns = { 'runtime', 'nvim', '.git', 'autoload', 'plugin' },
        runtimepath = true,
      },
      vimruntime = '',
      suggest = {
        fromVimruntime = true,
        fromRuntimepath = true,
      },
      iskeyword = '@,48-57,_,192-255,-#',
      diagnostic = {
        enable = true,
      },
    },
  },
}
