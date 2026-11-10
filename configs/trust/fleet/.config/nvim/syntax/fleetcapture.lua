-- Only lines starting with # are left out of the capture, so only those read as comments.
vim.cmd([[
  syntax match fleetcaptureComment /^#.*/
  highlight default link fleetcaptureComment Comment
]])
vim.b.current_syntax = 'fleetcapture'
