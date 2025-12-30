-- Auto-generated treesitter highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- Variables
    ['@variable'] = { fg = theme.ui.fg },
    ['@variable.builtin'] = { fg = theme.syn.special2, italic = true },
    ['@variable.parameter'] = { fg = theme.syn.parameter },
    ['@variable.member'] = { fg = theme.syn.identifier },

    -- Constants
    ['@constant'] = { link = 'Constant' },
    ['@constant.builtin'] = { fg = theme.syn.constant, bold = true },
    ['@constant.macro'] = { link = 'Macro' },

    -- Modules
    ['@module'] = { link = 'Structure' },
    ['@module.builtin'] = { fg = theme.syn.special1 },
    ['@label'] = { link = 'Label' },

    -- Strings
    ['@string'] = { link = 'String' },
    ['@string.documentation'] = { fg = theme.syn.string, italic = true },
    ['@string.regexp'] = { fg = theme.syn.regex },
    ['@string.escape'] = { fg = theme.syn.regex, bold = true },
    ['@string.special'] = { link = 'Special' },
    ['@string.special.symbol'] = { fg = theme.syn.identifier },
    ['@string.special.path'] = { link = 'Directory' },
    ['@string.special.url'] = { fg = theme.syn.special1, undercurl = true },

    -- Characters
    ['@character'] = { link = 'Character' },
    ['@character.special'] = { link = 'SpecialChar' },

    -- Booleans and numbers
    ['@boolean'] = { link = 'Boolean' },
    ['@number'] = { link = 'Number' },
    ['@number.float'] = { link = 'Float' },

    -- Types
    ['@type'] = { link = 'Type' },
    ['@type.builtin'] = { fg = theme.syn.type, italic = true },
    ['@type.definition'] = { link = 'Type' },

    -- Attributes
    ['@attribute'] = { link = 'Constant' },
    ['@attribute.builtin'] = { fg = theme.syn.special1 },
    ['@property'] = { fg = theme.syn.identifier },

    -- Functions
    ['@function'] = { link = 'Function' },
    ['@function.builtin'] = { fg = theme.syn.fun, italic = true },
    ['@function.call'] = { link = 'Function' },
    ['@function.macro'] = { link = 'Macro' },
    ['@function.method'] = { link = 'Function' },
    ['@function.method.call'] = { link = 'Function' },

    -- Constructors
    ['@constructor'] = { fg = theme.syn.special1 },
    ['@constructor.lua'] = { fg = theme.syn.keyword },

    -- Operators
    ['@operator'] = { link = 'Operator' },

    -- Keywords
    ['@keyword'] = { link = 'Keyword' },
    ['@keyword.coroutine'] = { fg = theme.syn.keyword, italic = true },
    ['@keyword.function'] = { fg = theme.syn.keyword },
    ['@keyword.operator'] = { fg = theme.syn.operator, bold = true },
    ['@keyword.import'] = { link = 'PreProc' },
    ['@keyword.type'] = { link = 'Type' },
    ['@keyword.modifier'] = { link = 'StorageClass' },
    ['@keyword.repeat'] = { link = 'Repeat' },
    ['@keyword.return'] = { fg = theme.syn.special3 },
    ['@keyword.debug'] = { link = 'Debug' },
    ['@keyword.exception'] = { fg = theme.syn.special3 },
    ['@keyword.conditional'] = { link = 'Conditional' },
    ['@keyword.conditional.ternary'] = { link = 'Operator' },
    ['@keyword.directive'] = { link = 'PreProc' },
    ['@keyword.directive.define'] = { link = 'Define' },

    -- Punctuation
    ['@punctuation.delimiter'] = { fg = theme.syn.punct },
    ['@punctuation.bracket'] = { fg = theme.syn.punct },
    ['@punctuation.special'] = { fg = theme.syn.special1 },

    -- Comments
    ['@comment'] = { link = 'Comment' },
    ['@comment.documentation'] = { fg = theme.syn.comment, italic = true },
    ['@comment.error'] = { fg = theme.ui.fg, bg = theme.diag.error, bold = true },
    ['@comment.warning'] = { fg = theme.ui.fg_reverse, bg = theme.diag.warning, bold = true },
    ['@comment.todo'] = { fg = theme.ui.fg_reverse, bg = theme.diag.hint, bold = true },
    ['@comment.note'] = { fg = theme.ui.fg_reverse, bg = theme.diag.info, bold = true },

    -- Markup
    ['@markup.strong'] = { bold = true },
    ['@markup.italic'] = { italic = true },
    ['@markup.strikethrough'] = { strikethrough = true },
    ['@markup.underline'] = { underline = true },
    ['@markup.heading'] = { link = 'Function' },
    ['@markup.quote'] = { fg = theme.syn.parameter, italic = true },
    ['@markup.math'] = { link = 'Constant' },
    ['@markup.environment'] = { link = 'Keyword' },
    ['@markup.link'] = { fg = theme.syn.special1 },
    ['@markup.link.label'] = { link = 'Special' },
    ['@markup.link.url'] = { fg = theme.syn.special1, undercurl = true },
    ['@markup.raw'] = { link = 'String' },
    ['@markup.raw.block'] = { fg = theme.syn.string },
    ['@markup.list'] = { fg = theme.syn.punct },
    ['@markup.list.checked'] = { fg = theme.diag.ok },
    ['@markup.list.unchecked'] = { fg = theme.ui.nontext },

    -- Diff
    ['@diff.plus'] = { fg = theme.vcs.added },
    ['@diff.minus'] = { fg = theme.vcs.removed },
    ['@diff.delta'] = { fg = theme.vcs.changed },

    -- Tags (HTML/XML)
    ['@tag'] = { link = 'Tag' },
    ['@tag.builtin'] = { fg = theme.syn.special3 },
    ['@tag.attribute'] = { fg = theme.syn.identifier },
    ['@tag.delimiter'] = { fg = theme.syn.punct },
  }
end

return M
