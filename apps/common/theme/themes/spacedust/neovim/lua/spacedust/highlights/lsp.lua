-- Auto-generated LSP semantic highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- LSP semantic tokens
    ['@lsp.type.class'] = { link = 'Structure' },
    ['@lsp.type.decorator'] = { link = 'Function' },
    ['@lsp.type.enum'] = { link = 'Structure' },
    ['@lsp.type.enumMember'] = { link = 'Constant' },
    ['@lsp.type.function'] = { link = 'Function' },
    ['@lsp.type.interface'] = { link = 'Structure' },
    ['@lsp.type.macro'] = { link = 'Macro' },
    ['@lsp.type.method'] = { link = '@function.method' },
    ['@lsp.type.namespace'] = { link = '@module' },
    ['@lsp.type.parameter'] = { link = '@variable.parameter' },
    ['@lsp.type.property'] = { link = '@property' },
    ['@lsp.type.struct'] = { link = 'Structure' },
    ['@lsp.type.type'] = { link = 'Type' },
    ['@lsp.type.typeParameter'] = { link = 'Type' },
    ['@lsp.type.variable'] = { fg = 'NONE' },
    ['@lsp.type.comment'] = { link = 'Comment' },

    ['@lsp.type.const'] = { link = 'Constant' },
    ['@lsp.type.comparison'] = { link = 'Operator' },
    ['@lsp.type.bitwise'] = { link = 'Operator' },
    ['@lsp.type.punctuation'] = { link = 'Delimiter' },

    ['@lsp.type.selfParameter'] = { link = '@variable.builtin' },
    ['@lsp.type.builtinConstant'] = { link = '@constant.builtin' },
    ['@lsp.type.magicFunction'] = { link = '@function.builtin' },

    -- Modifiers
    ['@lsp.mod.readonly'] = { link = 'Constant' },
    ['@lsp.mod.typeHint'] = { link = 'Type' },
    ['@lsp.mod.defaultLibrary'] = { link = 'Special' },
    ['@lsp.mod.builtin'] = { link = 'Special' },

    -- Type + modifier combinations
    ['@lsp.typemod.operator.controlFlow'] = { link = '@keyword.exception' },
    ['@lsp.type.lifetime'] = { link = 'Operator' },
    ['@lsp.typemod.keyword.documentation'] = { link = 'Special' },
    ['@lsp.type.decorator.rust'] = { link = 'PreProc' },

    ['@lsp.typemod.variable.global'] = { link = 'Constant' },
    ['@lsp.typemod.variable.static'] = { link = 'Constant' },
    ['@lsp.typemod.variable.defaultLibrary'] = { link = 'Special' },

    ['@lsp.typemod.function.builtin'] = { link = '@function.builtin' },
    ['@lsp.typemod.function.defaultLibrary'] = { link = '@function.builtin' },
    ['@lsp.typemod.method.defaultLibrary'] = { link = '@function.builtin' },

    ['@lsp.typemod.variable.injected'] = { link = '@variable' },
    ['@lsp.typemod.function.readonly'] = { fg = theme.syn.fun, bold = true },
  }
end

return M
