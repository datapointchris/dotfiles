-- Buffer notifications emitted during startup and replay them once the real
-- notifier is ready. fidget replaces vim.notify only after it loads, so
-- anything emitted before that — env errors, plugin build/version warnings
-- (e.g. blink.cmp), lazy.nvim output — would otherwise flash past as a raw vim
-- message and never enter the notification history. Buffering + replay makes
-- those early messages readable and recorded. Mirrors LazyVim's lazy_notify().
return function()
  local notifications = {}
  local function queue(...)
    table.insert(notifications, vim.F.pack_len(...))
  end

  local original_notify = vim.notify
  vim.notify = queue

  local timer = vim.uv.new_timer()
  local check = assert(vim.uv.new_check())

  local replay = function()
    timer:stop()
    check:stop()
    -- If nothing replaced vim.notify (no notifier), restore the original.
    if vim.notify == queue then
      vim.notify = original_notify
    end
    vim.schedule(function()
      for _, notification in ipairs(notifications) do
        vim.notify(vim.F.unpack_len(notification))
      end
    end)
  end

  -- Replay as soon as something (fidget) replaces vim.notify...
  check:start(function()
    if vim.notify ~= queue then
      replay()
    end
  end)
  -- ...or after 500ms if nothing does, so messages are never lost.
  timer:start(500, 0, replay)
end
