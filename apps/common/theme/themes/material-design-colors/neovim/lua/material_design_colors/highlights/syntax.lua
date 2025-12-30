-- Auto-generated syntax highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    Comment = { fg = theme.syn.comment, italic = true },

    Constant = { fg = theme.syn.constant },
    String = { fg = theme.syn.string },
    Character = { link = 'String' },
    Number = { fg = theme.syn.number },
    Boolean = { fg = theme.syn.constant, bold = true },
    Float = { link = 'Number' },

    Identifier = { fg = theme.syn.identifier },
    Function = { fg = theme.syn.fun },

    Statement = { fg = theme.syn.statement },
    Conditional = { link = 'Statement' },
    Repeat = { link = 'Statement' },
    Label = { link = 'Statement' },
    Operator = { fg = theme.syn.operator },
    Keyword = { fg = theme.syn.keyword },
    Exception = { fg = theme.syn.special2 },

    PreProc = { fg = theme.syn.preproc },
    Include = { link = 'PreProc' },
    Define = { link = 'PreProc' },
    Macro = { link = 'PreProc' },
    PreCondit = { link = 'PreProc' },

    Type = { fg = theme.syn.type },
    StorageClass = { link = 'Type' },
    Structure = { link = 'Type' },
    Typedef = { link = 'Type' },

    Special = { fg = theme.syn.special1 },
    SpecialChar = { link = 'Special' },
    Tag = { fg = theme.syn.special3 },
    Delimiter = { fg = theme.syn.punct },
    SpecialComment = { link = 'Special' },
    Debug = { fg = theme.diag.warning },

    Underlined = { fg = theme.syn.special1, underline = true },
    Bold = { bold = true },
    Italic = { italic = true },

    Ignore = { link = 'NonText' },
    Error = { fg = theme.diag.error },
    Todo = { fg = theme.ui.fg_reverse, bg = theme.diag.info, bold = true },

    qfLineNr = { link = 'LineNr' },
    qfFileName = { link = 'Directory' },

    markdownCode = { fg = theme.syn.string },
    markdownCodeBlock = { fg = theme.syn.string },
    markdownEscape = { fg = 'NONE' },
  }
end

return M
