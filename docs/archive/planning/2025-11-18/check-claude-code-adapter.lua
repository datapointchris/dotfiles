-- Check if codecompanion has a claude_code adapter
-- Run: nvim -c "luafile .planning/check-claude-code-adapter.lua" -c "q"

print('\n=== Checking for Claude Code Adapter ===\n')

local ok, adapters = pcall(require, 'codecompanion.adapters')
if not ok then
  print('❌ Could not load codecompanion.adapters')
  return
end

print('Available adapters:')
for name, _ in pairs(adapters) do
  print('  - ' .. name)
end

if adapters.claude_code then
  print('\n✅ claude_code adapter exists!')
  print('   This might work with your OAuth token.')
else
  print('\n❌ No claude_code adapter found.')
  print('   codecompanion requires ANTHROPIC_API_KEY')
end

print('\n')
