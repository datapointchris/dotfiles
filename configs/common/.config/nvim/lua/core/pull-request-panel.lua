-- The pull request beside its diff, in an nvim prs started to show a pull
-- request's diff.
--
-- prs writes the pull request's markdown document and its review threads to two
-- files, and names them in PRS_DIFF_DOCUMENT and PRS_DIFF_THREADS, which
-- core.profiles reads. Where PRS_DIFF_DOCUMENT was unset, setup() does nothing, so
-- every other nvim is untouched.
--
-- - <leader>gr shows the document in a split at the right edge, and hides it.
-- - <leader>gR shows it in a float, and hides it.
-- - <CR> or gf on a `path` or `path:line` mention in the document selects that file
--   in the open diffview, through its Lua API, and puts the cursor on the line.
--   Where the cursor is on no file the diff changes, the first backticked one on
--   the line is taken, then the nearest heading above, so a row of the files
--   table, a thread's heading and each line of its comments jump to it.
-- - Each review thread shows as virtual text at the end of its line, on the side of
--   the diff its `side` names: LEFT is the base's copy of the file, RIGHT the head's.
--   octo.nvim's reviews.show_virtual_text is the model.
--
-- The threads file is JSON. This reads its title, threads_read, and each thread's
-- path, line, side, resolved, comments and comment_count.

local profiles = require('core.profiles')

local M = {}

M.namespace = vim.api.nvim_create_namespace('pull-request-threads')

local state = {
  document = nil,
  threads = {},
  title = nil,
  buf = -1,
  panel = -1,
  float = -1,
}

local function say(message, level)
  vim.notify(message, level or vim.log.levels.INFO, { title = 'Pull request' })
end

-- A diff with no thread on it reads as a pull request nobody commented on, so each
-- way of ending up with no threads to show says so.
local function read_threads(path)
  if not path then
    say('prs named no review threads, so none show on the diff.', vim.log.levels.WARN)
    return {}
  end
  if vim.fn.filereadable(path) == 0 then
    say(path .. ' is gone, so no review threads show on the diff.', vim.log.levels.WARN)
    return {}
  end
  local ok, decoded = pcall(vim.json.decode, table.concat(vim.fn.readfile(path), '\n'), {
    luanil = { object = true, array = true },
  })
  if not ok or type(decoded) ~= 'table' then
    say('Could not read the review threads in ' .. path, vim.log.levels.WARN)
    return {}
  end
  state.title = decoded.title
  if decoded.threads_read == false then
    say('prs had not read the review threads when the diff opened, so none show on it.', vim.log.levels.WARN)
  end
  return decoded.threads or {}
end

-- The open DiffView: this tab's, or else the first one open.
local function diff_view()
  local loaded, lib = pcall(require, 'diffview.lib')
  if not loaded then
    return nil
  end
  local view = lib.get_current_view()
  if not view then
    view = lib.views[1]
  end
  if view and view.files and view.cur_layout then
    return view
  end
  return nil
end

local function thread_text(thread)
  local first = thread.comments and thread.comments[1]
  local who = first and first.author ~= '' and first.author or 'someone'
  local said = first and (first.body or ''):match('[^\r\n]+') or ''
  local text = '  ' .. who .. ': ' .. said
  local replies = (thread.comment_count or #(thread.comments or {})) - 1
  if replies > 0 then
    text = text .. (' (+%d)'):format(replies)
  end
  if thread.resolved then
    return { { text .. ' · resolved', 'Comment' } }
  end
  return { { text, 'DiagnosticVirtualTextInfo' } }
end

-- Puts each thread on the file the diff shows now, on both sides, and clears what an
-- earlier call put there. The entry's path is the head's, which is the path GitHub
-- gives a thread, so a renamed file's base side matches it too.
function M.decorate()
  local view = diff_view()
  local entry = view and view.cur_entry
  if not entry or not entry.layout then
    return
  end
  for side, symbol in pairs({ LEFT = 'a', RIGHT = 'b' }) do
    local window = entry.layout[symbol]
    local bufnr = window and window.file and window.file.bufnr
    if bufnr and vim.api.nvim_buf_is_valid(bufnr) then
      vim.api.nvim_buf_clear_namespace(bufnr, M.namespace, 0, -1)
      local count = vim.api.nvim_buf_line_count(bufnr)
      for _, thread in ipairs(state.threads) do
        if thread.path == entry.path and thread.side == side and type(thread.line) == 'number' and thread.line <= count then
          vim.api.nvim_buf_set_extmark(bufnr, M.namespace, thread.line - 1, 0, {
            virt_text = thread_text(thread),
            virt_text_pos = 'eol',
            hl_mode = 'combine',
          })
        end
      end
    end
  end
end

-- Each mention the cursor could mean, best first: the word under it, then each
-- backticked span on the line. A mention is a path with an optional :line.
local function mentions(text, col)
  local found = {}
  local function add(token)
    token = (token or ''):gsub('^%./', ''):gsub('[.:,;]+$', '')
    if token == '' then
      return
    end
    local path, line = token:match('^(.-):(%d+)$')
    if not path then
      path, line = token:match('^(.-):(%d+):%d+$')
    end
    table.insert(found, { path = path or token, line = tonumber(line) })
  end
  local stop = '[%s`|()%[%]<>"\',;*]'
  local first, last = col + 1, col + 1
  while first > 1 and not text:sub(first - 1, first - 1):match(stop) do
    first = first - 1
  end
  while last <= #text and not text:sub(last, last):match(stop) do
    last = last + 1
  end
  add(text:sub(first, last - 1))
  for span in text:gmatch('`([^`]+)`') do
    add(span)
  end
  return found
end

-- The path of the diff's file a mention names: the same path, wherever diffview
-- lists it, or else the one file whose path ends in it.
local function resolve(view, mentioned)
  local endings = {}
  for _, file in view.files:iter() do
    if file.path == mentioned then
      return file.path
    end
    if vim.endswith(file.path, '/' .. mentioned) then
      table.insert(endings, file.path)
    end
  end
  if #endings == 1 then
    return endings[1]
  end
  return nil
end

-- The first of the mentions that names a file the diff changes, and its line.
local function first_resolved(view, found)
  for _, mention in ipairs(found) do
    local path = resolve(view, mention.path)
    if path then
      return path, mention.line
    end
  end
  return nil
end

-- What a jump that found no file says: the first mention shaped like a path, since
-- the word under the cursor may be any word in a comment.
local function refusal(found)
  for _, mention in ipairs(found) do
    if mention.path:find('[/.]') then
      return mention.path .. ' is not a file this diff changes.'
    end
  end
  return 'No file this diff changes is named on this line.'
end

local function side_of(path, line)
  for _, thread in ipairs(state.threads) do
    if thread.path == path and thread.line == line then
      return thread.side
    end
  end
  return 'RIGHT'
end

-- An entry's layout holds its files, and the view's current layout holds the windows
-- they are shown in.
local function place_cursor(view, path, line)
  local entry = view.cur_entry
  if not entry or entry.path ~= path then
    return
  end
  local window = side_of(path, line) == 'LEFT' and view.cur_layout.a or view.cur_layout.b
  if not (window and window.id and vim.api.nvim_win_is_valid(window.id)) then
    return
  end
  local count = vim.api.nvim_buf_line_count(vim.api.nvim_win_get_buf(window.id))
  vim.api.nvim_set_current_win(window.id)
  vim.api.nvim_win_set_cursor(window.id, { math.min(line, count), 0 })
  vim.cmd('normal! zz')
end

-- Selects the file the line under the cursor mentions in the open diffview. A line
-- naming none takes the nearest heading above it, which for a thread's comments is
-- the thread's own path:line.
function M.jump()
  local view = diff_view()
  if not view then
    say('No diffview is open to jump in.', vim.log.levels.WARN)
    return
  end
  local row, col = unpack(vim.api.nvim_win_get_cursor(0))
  local here = mentions(vim.api.nvim_get_current_line(), col)
  local path, line = first_resolved(view, here)
  if not path then
    for _, text in ipairs(vim.fn.reverse(vim.api.nvim_buf_get_lines(0, 0, row, false))) do
      if text:match('^#+%s') then
        path, line = first_resolved(view, mentions(text, 0))
        break
      end
    end
  end
  if not path then
    say(refusal(here), vim.log.levels.WARN)
    return
  end
  if vim.api.nvim_win_is_valid(state.float) and vim.api.nvim_get_current_win() == state.float then
    vim.api.nvim_win_close(state.float, true)
  end
  if vim.api.nvim_get_current_tabpage() ~= view.tabpage then
    vim.api.nvim_set_current_tabpage(view.tabpage)
  end
  local async = require('diffview.async')
  async.void(function()
    async.await(view:set_file_by_path(path, true, true))
    if line then
      vim.schedule(function()
        place_cursor(view, path, line)
      end)
    end
  end)()
end

local function document_buffer()
  if vim.api.nvim_buf_is_valid(state.buf) then
    return state.buf
  end
  if vim.fn.filereadable(state.document) == 0 then
    say(state.document .. ' is gone, so there is no pull request to show.', vim.log.levels.WARN)
    return nil
  end
  local buf = vim.fn.bufadd(state.document)
  vim.bo[buf].swapfile = false
  vim.fn.bufload(buf)
  vim.bo[buf].filetype = 'markdown'
  vim.bo[buf].modifiable = false
  vim.bo[buf].readonly = true
  vim.bo[buf].bufhidden = 'hide'
  for _, key in ipairs({ '<CR>', 'gf' }) do
    vim.keymap.set('n', key, M.jump, { buffer = buf, desc = 'Pull request: select this file in the diff' })
  end
  state.buf = buf
  return buf
end

-- A window split off a diff window inherits its diff, scrollbind and folds, which
-- would bind the document to the diff's scrolling.
local function dress(win)
  local wo = vim.wo[win][0]
  wo.diff = false
  wo.scrollbind = false
  wo.cursorbind = false
  wo.foldenable = false
  wo.wrap = true
  wo.linebreak = true
  wo.number = false
  wo.relativenumber = false
  wo.signcolumn = 'no'
end

local function shown_here(win)
  return vim.api.nvim_win_is_valid(win) and vim.api.nvim_win_get_tabpage(win) == vim.api.nvim_get_current_tabpage()
end

function M.toggle_panel()
  if shown_here(state.panel) then
    vim.api.nvim_win_close(state.panel, true)
    state.panel = -1
    return
  end
  if vim.api.nvim_win_is_valid(state.panel) then
    vim.api.nvim_win_close(state.panel, true)
  end
  local buf = document_buffer()
  if not buf then
    return
  end
  state.panel = vim.api.nvim_open_win(buf, true, {
    split = 'right',
    win = -1,
    width = math.max(40, math.floor(vim.o.columns * 0.4)),
  })
  dress(state.panel)
  vim.wo[state.panel][0].winfixwidth = true
end

function M.toggle_float()
  if vim.api.nvim_win_is_valid(state.float) then
    vim.api.nvim_win_close(state.float, true)
    state.float = -1
    return
  end
  local buf = document_buffer()
  if not buf then
    return
  end
  local width = math.floor(vim.o.columns * 0.8)
  local height = math.floor(vim.o.lines * 0.8)
  state.float = vim.api.nvim_open_win(buf, true, {
    relative = 'editor',
    width = width,
    height = height,
    col = math.floor((vim.o.columns - width) / 2),
    row = math.floor((vim.o.lines - height) / 2),
    border = 'rounded',
    title = state.title and (' ' .. state.title .. ' ') or nil,
    title_pos = state.title and 'center' or nil,
  })
  dress(state.float)
end

-- Maps the keys and hangs the threads on the diff, in a pull request's diff alone.
function M.setup()
  local diff = profiles.pull_request_diff
  if not diff then
    return
  end
  state.document = diff.document
  state.threads = read_threads(diff.threads)
  vim.keymap.set('n', '<leader>gr', M.toggle_panel, { desc = 'Git: pull request beside the diff' })
  vim.keymap.set('n', '<leader>gR', M.toggle_float, { desc = 'Git: pull request in a float' })
  vim.api.nvim_create_autocmd('User', {
    desc = 'Pull request: show its review threads on the diff',
    group = vim.api.nvim_create_augroup('pull-request-threads', { clear = true }),
    pattern = { 'DiffviewDiffBufWinEnter', 'DiffviewViewEnter' },
    callback = M.decorate,
  })
end

return M
