-- The pull request beside a diff prs opened, driven in a headless Neovim against a
-- real git repo and the diffview.nvim lazy installed. Run it directly:
--   nvim --headless -u NONE -l tests/nvim/pull_request_panel_spec.lua
-- It exits non-zero on a failure, so the commit hook gates on it. Where lazy has not
-- installed diffview.nvim there is no diff to drive, so it says so and passes.

local repo_root = vim.fn.fnamemodify(debug.getinfo(1, 'S').source:sub(2), ':p:h:h:h')
vim.opt.runtimepath:prepend(repo_root .. '/configs/common/.config/nvim')

-- print loses its newline once diffview has drawn, so each line is written whole.
local function say(line)
  io.stdout:write(line .. '\n')
end

local diffview = vim.fn.stdpath('data') .. '/lazy/diffview.nvim'
if vim.fn.isdirectory(diffview) == 0 then
  say('SKIP diffview.nvim is not at ' .. diffview .. ', where lazy installs it the first time nvim starts')
  vim.cmd('qall!')
end
vim.opt.runtimepath:prepend(diffview)
vim.cmd.runtime('plugin/diffview.lua')
vim.g.mapleader = ' '

local failures = {}
local function check(name, ok)
  if not ok then
    table.insert(failures, name)
  end
  say((ok and 'ok   ' or 'FAIL ') .. name)
end

-- What the checks stand on. Without it the checks after it say nothing.
local function needs(what, ok)
  if not ok then
    say('FAIL ' .. what)
    vim.cmd('cquit')
  end
end

local said = {}
vim.notify = function(message, level, _)
  table.insert(said, { text = message, level = level })
end

local function press(keys)
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(keys, true, false, true), 'x', false)
end

-- git exports its repository variables when it runs a hook, naming the repo being
-- committed. Left set, every git below and every git diffview runs would act on
-- that repo rather than the one built here.
for _, name in ipairs(vim.fn.systemlist({ 'git', 'rev-parse', '--local-env-vars' })) do
  vim.env[name] = nil
end

local tmp = vim.fn.tempname()
vim.fn.mkdir(tmp, 'p')

-- A branch that changes line 3 of cache/cache.go and adds lines 13 to 15, adds
-- cache/metrics.go, and changes a main.go at the root and one in each of cmd/a and
-- cmd/b.
local repo = tmp .. '/widget'
for _, dir in ipairs({ '/cache', '/cmd/a', '/cmd/b' }) do
  vim.fn.mkdir(repo .. dir, 'p')
end
local function git(...)
  local out = vim.fn.system(vim.list_extend({
    'git',
    '-C',
    repo,
    '-c',
    'user.name=spec',
    '-c',
    'user.email=spec@example.com',
    '-c',
    'commit.gpgsign=false',
    '-c',
    'core.hooksPath=/dev/null',
  }, { ... }))
  assert(vim.v.shell_error == 0, out)
end
local base = { 'package cache', '', 'import "time"' }
for n = 4, 12 do
  table.insert(base, '// line ' .. n)
end
local head = vim.list_extend(vim.deepcopy(base), { '// line 13', '// line 14 reads the wall clock', '// line 15' })
head[3] = 'import "sync"'
local mains = { 'main.go', 'cmd/a/main.go', 'cmd/b/main.go' }
git('init', '--quiet', '-b', 'main')
local made = vim.trim(vim.fn.system({ 'git', '-C', repo, 'rev-parse', '--absolute-git-dir' }))
needs('git init made ' .. made .. ' rather than a repo in ' .. repo, made == vim.fn.resolve(repo) .. '/.git')
vim.fn.writefile(base, repo .. '/cache/cache.go')
for _, main in ipairs(mains) do
  vim.fn.writefile({ 'package main' }, repo .. '/' .. main)
end
git('add', '.')
git('commit', '--quiet', '-m', 'base')
git('checkout', '--quiet', '-b', 'cache-metrics')
vim.fn.writefile(head, repo .. '/cache/cache.go')
vim.fn.writefile({ 'package cache', '', 'var hits int' }, repo .. '/cache/metrics.go')
for _, main in ipairs(mains) do
  vim.fn.writefile({ 'package main', '', 'func main() {}' }, repo .. '/' .. main)
end
git('add', '.')
git('commit', '--quiet', '-m', 'head')

-- A document and a threads file shaped like the ones prs writes.
local document = tmp .. '/prs-diff-widget-13.md'
vim.fn.writefile({
  '# Count cache hits',
  '',
  '`acme/widget` #13 · opened by octo · `cache-metrics` into `main`',
  '',
  '# Description',
  '',
  'The counter lives in metrics.go, and the design is in `docs/design.md`.',
  '',
  '# Files',
  '',
  '| File | Change | Added | Removed |',
  '| --- | --- | ---: | ---: |',
  '| `cache/cache.go` | modified | 4 | 1 |',
  '| `cache/metrics.go` | added | 3 | 0 |',
  '| `cmd/a/main.go` | modified | 2 | 0 |',
  '| `cmd/b/main.go` | modified | 2 | 0 |',
  '| `main.go` | modified | 2 | 0 |',
  '',
  '# Comments',
  '',
  '## Review threads',
  '',
  '2 of 3 unresolved.',
  '',
  '### `cache/cache.go:14` · unresolved',
  '',
  '**mona** · 3h ago',
  '',
  'This expiry reads the wall clock.',
  'Take a clock instead.',
  '',
  '**octo** · 2h ago',
  '',
  'Done.',
  '',
  '### `cache/cache.go`, on a line gone from the diff · unresolved, outdated',
  '',
  '**mona** · 3h ago',
  '',
  'This line moved.',
  '',
  '### `cache/cache.go:3` · resolved',
  '',
  '**hubot** · 3h ago',
  '',
  'Why did the time import go?',
}, document)
local function comment(author, body)
  return { author = author, body = body, created_at = '2026-11-02T10:14:00Z', url = 'https://github.com/acme/widget/pull/13#discussion_r1' }
end
local function threads_file(name, threads_read, threads)
  local path = tmp .. '/' .. name
  vim.fn.writefile({
    vim.json.encode({
      slug = 'acme/widget',
      number = 13,
      title = 'Count cache hits',
      url = 'https://github.com/acme/widget/pull/13',
      base = 'origin/main',
      head = '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b',
      threads_read = threads_read,
      threads = threads,
    }),
  }, path)
  return path
end
local threads = threads_file('prs-diff-widget-13.threads.json', true, {
  {
    path = 'cache/cache.go',
    line = 14,
    side = 'RIGHT',
    resolved = false,
    outdated = false,
    comments = { comment('mona', 'This expiry reads the wall clock.\nTake a clock instead.'), comment('octo', 'Done.') },
    comment_count = 2,
  },
  {
    path = 'cache/cache.go',
    line = 3,
    side = 'LEFT',
    resolved = true,
    outdated = false,
    comments = { comment('hubot', 'Why did the time import go?') },
    comment_count = 1,
  },
  {
    path = 'cache/cache.go',
    line = vim.NIL,
    side = 'RIGHT',
    resolved = false,
    outdated = true,
    comments = { comment('mona', 'This line moved.') },
    comment_count = 1,
  },
})
local threads_unread = threads_file('prs-diff-widget-13.unread.threads.json', false, {})

-- Loads the config's modules afresh, as an nvim started with these variables would.
local function started_with(document_path, threads_path)
  vim.env.PRS_DIFF_DOCUMENT = document_path
  vim.env.PRS_DIFF_THREADS = threads_path
  package.loaded['core.profiles'] = nil
  package.loaded['core.pull-request-panel'] = nil
  local panel = require('core.pull-request-panel')
  panel.setup()
  return panel
end

started_with(nil, nil)
check('an nvim prs did not start maps no pull request key', vim.fn.maparg(' gr', 'n') == '')

said = {}
started_with(document, threads_unread)
check('a diff opened before prs read the review threads warns that none show', #said == 1 and said[1].level == vim.log.levels.WARN)

said = {}
local panel = started_with(document, threads)
check(
  'a program the diff nvim starts is an ordinary one, with no PRS_DIFF_DOCUMENT',
  vim.trim(vim.fn.system({ 'printenv', 'PRS_DIFF_DOCUMENT' })) == ''
)

vim.cmd.cd(repo)
vim.cmd('DiffviewOpen main...cache-metrics')
local lib = require('diffview.lib')
local function view()
  return lib.get_current_view()
end
local function showing(path)
  return vim.wait(5000, function()
    local v = view()
    local entry = v and v.cur_entry
    local b = entry and entry.path == path and entry.layout.b
    return b and b.file and b.file.bufnr and vim.api.nvim_buf_line_count(b.file.bufnr) > 1 or false
  end, 20)
end
needs('the diff opens on cache/cache.go', showing('cache/cache.go'))

local function marks(symbol)
  local bufnr = view().cur_entry.layout[symbol].file.bufnr
  local found = {}
  for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(bufnr, panel.namespace, 0, -1, { details = true })) do
    table.insert(found, { row = mark[2], text = mark[4].virt_text[1][1] })
  end
  return found
end
vim.wait(2000, function()
  return #marks('b') > 0 and #marks('a') > 0
end, 20)
local right, left = marks('b'), marks('a')
check(
  "a RIGHT thread shows on its line of the head's copy, with its reply count",
  #right == 1 and right[1].row == 13 and right[1].text == '  mona: This expiry reads the wall clock. (+1)'
)
check(
  "a LEFT thread shows on its line of the base's copy, marked resolved",
  #left == 1 and left[1].row == 2 and left[1].text == '  hubot: Why did the time import go? · resolved'
)

local function windows_showing_document()
  local found = {}
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(win)) == document then
      table.insert(found, win)
    end
  end
  return found
end

press(' gr')
local shown = windows_showing_document()
local win = shown[1]
check(
  '<leader>gr shows the document in a split at the right edge, unbound from the diff',
  #shown == 1
    and vim.api.nvim_win_get_config(win).relative == ''
    and vim.api.nvim_win_get_position(win)[2] + vim.api.nvim_win_get_width(win) == vim.o.columns
    and not vim.wo[win].diff
    and not vim.wo[win].scrollbind
)
press(' gr')
check('<leader>gr again hides it', #windows_showing_document() == 0)

press(' gR')
shown = windows_showing_document()
check('<leader>gR shows the document in a float', #shown == 1 and vim.api.nvim_win_get_config(shown[1]).relative == 'editor')
press(' gR')
check('<leader>gR again hides it', #windows_showing_document() == 0)

-- Puts the cursor in the document on the first line holding text, at its column.
local function on(text)
  local document_win = windows_showing_document()[1]
  vim.api.nvim_set_current_win(document_win)
  for row, line in ipairs(vim.api.nvim_buf_get_lines(0, 0, -1, false)) do
    local col = line:find(text, 1, true)
    if col then
      vim.api.nvim_win_set_cursor(document_win, { row, col - 1 })
      return
    end
  end
  error(text .. ' is not in the document')
end

local function at(path, symbol, row)
  return vim.wait(5000, function()
    local entry = view().cur_entry
    if entry.path ~= path then
      return false
    end
    local window = view().cur_layout[symbol]
    return vim.api.nvim_get_current_win() == window.id and vim.api.nvim_win_get_cursor(window.id)[1] == row
  end, 20)
end

press(' gr')
on('metrics.go, and')
press('<CR>')
check('a bare file name under the cursor selects the one file it ends', showing('cache/metrics.go'))

on('| `cache/cache.go`')
press('<CR>')
check('a row of the files table selects its file from the start of the row', showing('cache/cache.go'))

on('| `main.go`')
press('<CR>')
check('a root file selects itself where nested files share its name', showing('main.go'))

on('Take a clock instead.')
press('<CR>')
check("a RIGHT thread's comment puts the cursor on its heading's line of the head's copy", at('cache/cache.go', 'b', 14))

on('### `cache/cache.go:3`')
press('gf')
check("gf on a LEFT thread's path:line puts the cursor on that line of the base's copy", at('cache/cache.go', 'a', 3))

said = {}
on('docs/design.md')
press('<CR>')
check(
  'a path the diff does not change is named in a notice, and the diff stays on its file',
  #said == 1 and said[1].text:find('docs/design.md', 1, true) ~= nil and view().cur_entry.path == 'cache/cache.go'
)

press(' gr')
press(' gR')
on('| `cache/metrics.go`')
press('<CR>')
check('a jump from the float closes it', showing('cache/metrics.go') and #windows_showing_document() == 0)

vim.fn.delete(tmp, 'rf')
if #failures > 0 then
  say('FAILED: ' .. table.concat(failures, ', '))
  vim.cmd('cquit')
end
