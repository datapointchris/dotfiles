#!/usr/bin/env python3
"""Generate Neovim colorscheme from theme.yml.

Creates a standalone Neovim colorscheme plugin that can be loaded via Lazy.nvim.
"""

import os
import re
from pathlib import Path

import yaml


def load_theme(theme_path: Path) -> dict:
    """Load theme.yml file."""
    with open(theme_path) as f:
        return yaml.safe_load(f)


def slug_to_module(slug: str) -> str:
    """Convert slug to valid Lua module name."""
    return slug.replace("-", "_")


def generate_palette_lua(theme: dict) -> str:
    """Generate palette.lua from theme.yml."""
    meta = theme.get("meta", {})
    base16 = theme.get("base16", {})
    extended = theme.get("extended", {})
    special = theme.get("special", {})

    lines = [
        "-- Auto-generated palette from theme.yml",
        f"-- Theme: {meta.get('name', 'Unknown')}",
        f"-- Source: {meta.get('source', 'Unknown')}",
        "",
        "local M = {}",
        "",
        "M.palette = {",
    ]

    # Base16 colors
    lines.append("  -- Base16 palette")
    for i in range(16):
        slot = f"base{i:02X}"
        color = base16.get(slot, "#000000")
        lines.append(f'  {slot} = "{color}",')

    # Extended colors
    if extended:
        lines.append("")
        lines.append("  -- Extended palette")
        for key, color in extended.items():
            if isinstance(color, str) and color.startswith("#"):
                lines.append(f'  {key} = "{color}",')

    lines.append("}")
    lines.append("")

    # Special colors
    lines.append("M.special = {")
    for key, color in special.items():
        if isinstance(color, str):
            lines.append(f'  {key} = "{color}",')
    lines.append("}")
    lines.append("")

    # Theme colors (semantic mapping from base16)
    lines.extend([
        "-- Semantic theme colors derived from palette",
        "M.theme = {",
        "  ui = {",
        f'    bg = M.palette.base00,',
        f'    bg_dim = M.palette.bg_dim or M.palette.base00,',
        f'    bg_p1 = M.palette.base01,',
        f'    bg_p2 = M.palette.base02,',
        f'    bg_m1 = M.palette.base01,',
        f'    bg_m3 = M.palette.base01,',
        f'    bg_gutter = M.palette.base00,',
        f'    bg_visual = M.palette.base02,',
        f'    bg_search = M.palette.base0A,',
        f'    fg = M.palette.base05,',
        f'    fg_dim = M.palette.base04,',
        f'    fg_reverse = M.palette.base00,',
        f'    special = M.palette.base0C,',
        f'    nontext = M.palette.base03,',
        f'    whitespace = M.palette.base02,',
        "    float = {",
        f'      fg = M.palette.base05,',
        f'      bg = M.palette.base01,',
        f'      fg_border = M.palette.base04,',
        f'      bg_border = M.palette.base01,',
        "    },",
        "    pmenu = {",
        f'      fg = M.palette.base05,',
        f'      fg_sel = M.palette.base05,',
        f'      bg = M.palette.base01,',
        f'      bg_sel = M.palette.base02,',
        f'      bg_sbar = M.palette.base02,',
        f'      bg_thumb = M.palette.base03,',
        "    },",
        "  },",
        "  syn = {",
        f'    comment = M.palette.base03,',
        f'    string = M.palette.base0B,',
        f'    number = M.palette.base0E,',
        f'    constant = M.palette.base0E,',
        f'    identifier = M.palette.base0D,',
        f'    parameter = M.palette.base0D,',
        f'    fun = M.palette.base0B,',
        f'    statement = M.palette.base08,',
        f'    keyword = M.palette.base08,',
        f'    operator = M.palette.base09,',
        f'    preproc = M.palette.base0C,',
        f'    type = M.palette.base0A,',
        f'    special1 = M.palette.base09,',
        f'    special2 = M.palette.base08,',
        f'    special3 = M.palette.base0C,',
        f'    punct = M.palette.base09,',
        f'    regex = M.palette.base0C,',
        f'    deprecated = M.palette.base03,',
        "  },",
        "  diag = {",
        f'    error = M.palette.base08,',
        f'    warning = M.palette.base09,',
        f'    info = M.palette.base0D,',
        f'    hint = M.palette.base0C,',
        f'    ok = M.palette.base0B,',
        "  },",
        "  vcs = {",
        f'    added = M.palette.base0B,',
        f'    changed = M.palette.base0A,',
        f'    removed = M.palette.base08,',
        "  },",
        "  diff = {",
        f'    add = M.palette.base0B,',
        f'    change = M.palette.base0A,',
        f'    delete = M.palette.base08,',
        f'    text = M.palette.base0D,',
        "  },",
        "}",
        "",
        "return M",
    ])

    return "\n".join(lines)


def generate_editor_lua() -> str:
    """Generate editor.lua with UI highlight groups."""
    return '''-- Auto-generated editor highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- Basic UI
    ColorColumn = { bg = theme.ui.bg_p1 },
    Conceal = { fg = theme.ui.special, bold = true },
    CurSearch = { fg = theme.ui.fg, bg = theme.ui.bg_search, bold = true },
    Cursor = { fg = theme.ui.bg, bg = theme.ui.fg },
    lCursor = { link = "Cursor" },
    CursorIM = { link = "Cursor" },
    CursorColumn = { link = "CursorLine" },
    CursorLine = { bg = theme.ui.bg_p2 },
    Directory = { fg = theme.syn.fun },

    -- Diff
    DiffAdd = { bg = theme.diff.add },
    DiffChange = { bg = theme.diff.change },
    DiffDelete = { fg = theme.vcs.removed, bg = theme.diff.delete },
    DiffText = { bg = theme.diff.text },

    EndOfBuffer = { fg = theme.ui.bg },
    ErrorMsg = { fg = theme.diag.error },
    WinSeparator = { fg = theme.ui.bg_m3 },
    VertSplit = { link = "WinSeparator" },
    Folded = { fg = theme.ui.special, bg = theme.ui.bg_p1 },
    FoldColumn = { fg = theme.ui.nontext, bg = theme.ui.bg_gutter },
    SignColumn = { fg = theme.ui.special, bg = theme.ui.bg_gutter },

    -- Search
    IncSearch = { fg = theme.ui.fg_reverse, bg = theme.diag.warning },
    Substitute = { fg = theme.ui.fg, bg = theme.vcs.removed },

    -- Line numbers
    LineNr = { fg = theme.ui.nontext, bg = theme.ui.bg_gutter },
    CursorLineNr = { fg = theme.diag.warning, bg = theme.ui.bg_gutter, bold = true },

    MatchParen = { fg = theme.diag.warning, bold = true },
    ModeMsg = { fg = theme.diag.warning, bold = true },
    MsgArea = { fg = theme.ui.fg_dim },
    MsgSeparator = { bg = theme.ui.bg_m3, fg = theme.ui.bg_m3 },
    MoreMsg = { fg = theme.diag.info },
    NonText = { fg = theme.ui.nontext },

    -- Normal
    Normal = { fg = theme.ui.fg, bg = theme.ui.bg },
    NormalFloat = { fg = theme.ui.float.fg, bg = theme.ui.float.bg },
    FloatBorder = { fg = theme.ui.float.fg_border, bg = theme.ui.float.bg_border },
    FloatTitle = { fg = theme.ui.special, bg = theme.ui.float.bg_border, bold = true },
    FloatFooter = { fg = theme.ui.nontext, bg = theme.ui.float.bg_border },
    NormalNC = { link = "Normal" },

    -- Popup menu
    Pmenu = { fg = theme.ui.pmenu.fg, bg = theme.ui.pmenu.bg },
    PmenuSel = { fg = theme.ui.pmenu.fg_sel, bg = theme.ui.pmenu.bg_sel },
    PmenuKind = { fg = theme.ui.fg_dim, bg = theme.ui.pmenu.bg },
    PmenuKindSel = { fg = theme.ui.fg_dim, bg = theme.ui.pmenu.bg_sel },
    PmenuExtra = { fg = theme.ui.special, bg = theme.ui.pmenu.bg },
    PmenuExtraSel = { fg = theme.ui.special, bg = theme.ui.pmenu.bg_sel },
    PmenuSbar = { bg = theme.ui.pmenu.bg_sbar },
    PmenuThumb = { bg = theme.ui.pmenu.bg_thumb },
    PmenuBorder = { link = "FloatBorder" },

    Question = { link = "MoreMsg" },
    QuickFixLine = { bg = theme.ui.bg_p1 },
    Search = { fg = theme.ui.fg, bg = theme.ui.bg_search },
    SpecialKey = { fg = theme.ui.special },

    -- Spell
    SpellBad = { undercurl = true, sp = theme.diag.error },
    SpellCap = { undercurl = true, sp = theme.diag.warning },
    SpellLocal = { undercurl = true, sp = theme.diag.warning },
    SpellRare = { undercurl = true, sp = theme.diag.warning },

    -- Status line
    StatusLine = { fg = theme.ui.fg_dim, bg = theme.ui.bg_m3 },
    StatusLineNC = { fg = theme.ui.nontext, bg = theme.ui.bg_m3 },

    -- Tab line
    TabLine = { bg = theme.ui.bg_m3, fg = theme.ui.special },
    TabLineFill = { bg = theme.ui.bg },
    TabLineSel = { fg = theme.ui.fg_dim, bg = theme.ui.bg_p1 },

    Title = { fg = theme.syn.fun, bold = true },
    Visual = { bg = theme.ui.bg_visual },
    VisualNOS = { link = "Visual" },
    WarningMsg = { fg = theme.diag.warning },
    Whitespace = { fg = theme.ui.whitespace },
    WildMenu = { link = "Pmenu" },
    WinBar = { fg = theme.ui.fg_dim, bg = "NONE" },
    WinBarNC = { fg = theme.ui.fg_dim, bg = "NONE" },

    -- Debug
    debugPC = { bg = theme.diff.delete },
    debugBreakpoint = { fg = theme.syn.special1, bg = theme.ui.bg_gutter },

    -- LSP references
    LspReferenceText = { bg = theme.diff.text },
    LspReferenceRead = { link = "LspReferenceText" },
    LspReferenceWrite = { bg = theme.diff.text, underline = true },

    -- Diagnostics
    DiagnosticError = { fg = theme.diag.error },
    DiagnosticWarn = { fg = theme.diag.warning },
    DiagnosticInfo = { fg = theme.diag.info },
    DiagnosticHint = { fg = theme.diag.hint },
    DiagnosticOk = { fg = theme.diag.ok },

    DiagnosticFloatingError = { fg = theme.diag.error },
    DiagnosticFloatingWarn = { fg = theme.diag.warning },
    DiagnosticFloatingInfo = { fg = theme.diag.info },
    DiagnosticFloatingHint = { fg = theme.diag.hint },
    DiagnosticFloatingOk = { fg = theme.diag.ok },

    DiagnosticSignError = { fg = theme.diag.error, bg = theme.ui.bg_gutter },
    DiagnosticSignWarn = { fg = theme.diag.warning, bg = theme.ui.bg_gutter },
    DiagnosticSignInfo = { fg = theme.diag.info, bg = theme.ui.bg_gutter },
    DiagnosticSignHint = { fg = theme.diag.hint, bg = theme.ui.bg_gutter },

    DiagnosticVirtualTextError = { link = "DiagnosticError" },
    DiagnosticVirtualTextWarn = { link = "DiagnosticWarn" },
    DiagnosticVirtualTextInfo = { link = "DiagnosticInfo" },
    DiagnosticVirtualTextHint = { link = "DiagnosticHint" },

    DiagnosticUnderlineError = { undercurl = true, sp = theme.diag.error },
    DiagnosticUnderlineWarn = { undercurl = true, sp = theme.diag.warning },
    DiagnosticUnderlineInfo = { undercurl = true, sp = theme.diag.info },
    DiagnosticUnderlineHint = { undercurl = true, sp = theme.diag.hint },

    LspSignatureActiveParameter = { fg = theme.diag.warning },
    LspCodeLens = { fg = theme.syn.comment },

    -- VCS
    diffAdded = { fg = theme.vcs.added },
    diffRemoved = { fg = theme.vcs.removed },
    diffDeleted = { fg = theme.vcs.removed },
    diffChanged = { fg = theme.vcs.changed },
    diffOldFile = { fg = theme.vcs.removed },
    diffNewFile = { fg = theme.vcs.added },
  }
end

return M
'''


def generate_syntax_lua() -> str:
    """Generate syntax.lua with traditional Vim syntax groups."""
    return '''-- Auto-generated syntax highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    Comment = { fg = theme.syn.comment, italic = true },

    Constant = { fg = theme.syn.constant },
    String = { fg = theme.syn.string },
    Character = { link = "String" },
    Number = { fg = theme.syn.number },
    Boolean = { fg = theme.syn.constant, bold = true },
    Float = { link = "Number" },

    Identifier = { fg = theme.syn.identifier },
    Function = { fg = theme.syn.fun },

    Statement = { fg = theme.syn.statement },
    Conditional = { link = "Statement" },
    Repeat = { link = "Statement" },
    Label = { link = "Statement" },
    Operator = { fg = theme.syn.operator },
    Keyword = { fg = theme.syn.keyword },
    Exception = { fg = theme.syn.special2 },

    PreProc = { fg = theme.syn.preproc },
    Include = { link = "PreProc" },
    Define = { link = "PreProc" },
    Macro = { link = "PreProc" },
    PreCondit = { link = "PreProc" },

    Type = { fg = theme.syn.type },
    StorageClass = { link = "Type" },
    Structure = { link = "Type" },
    Typedef = { link = "Type" },

    Special = { fg = theme.syn.special1 },
    SpecialChar = { link = "Special" },
    Tag = { fg = theme.syn.special3 },
    Delimiter = { fg = theme.syn.punct },
    SpecialComment = { link = "Special" },
    Debug = { fg = theme.diag.warning },

    Underlined = { fg = theme.syn.special1, underline = true },
    Bold = { bold = true },
    Italic = { italic = true },

    Ignore = { link = "NonText" },
    Error = { fg = theme.diag.error },
    Todo = { fg = theme.ui.fg_reverse, bg = theme.diag.info, bold = true },

    qfLineNr = { link = "LineNr" },
    qfFileName = { link = "Directory" },

    markdownCode = { fg = theme.syn.string },
    markdownCodeBlock = { fg = theme.syn.string },
    markdownEscape = { fg = "NONE" },
  }
end

return M
'''


def generate_treesitter_lua() -> str:
    """Generate treesitter.lua with @capture groups."""
    return '''-- Auto-generated treesitter highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- Variables
    ["@variable"] = { fg = theme.ui.fg },
    ["@variable.builtin"] = { fg = theme.syn.special2, italic = true },
    ["@variable.parameter"] = { fg = theme.syn.parameter },
    ["@variable.member"] = { fg = theme.syn.identifier },

    -- Constants
    ["@constant"] = { link = "Constant" },
    ["@constant.builtin"] = { fg = theme.syn.constant, bold = true },
    ["@constant.macro"] = { link = "Macro" },

    -- Modules
    ["@module"] = { link = "Structure" },
    ["@module.builtin"] = { fg = theme.syn.special1 },
    ["@label"] = { link = "Label" },

    -- Strings
    ["@string"] = { link = "String" },
    ["@string.documentation"] = { fg = theme.syn.string, italic = true },
    ["@string.regexp"] = { fg = theme.syn.regex },
    ["@string.escape"] = { fg = theme.syn.regex, bold = true },
    ["@string.special"] = { link = "Special" },
    ["@string.special.symbol"] = { fg = theme.syn.identifier },
    ["@string.special.path"] = { link = "Directory" },
    ["@string.special.url"] = { fg = theme.syn.special1, undercurl = true },

    -- Characters
    ["@character"] = { link = "Character" },
    ["@character.special"] = { link = "SpecialChar" },

    -- Booleans and numbers
    ["@boolean"] = { link = "Boolean" },
    ["@number"] = { link = "Number" },
    ["@number.float"] = { link = "Float" },

    -- Types
    ["@type"] = { link = "Type" },
    ["@type.builtin"] = { fg = theme.syn.type, italic = true },
    ["@type.definition"] = { link = "Type" },

    -- Attributes
    ["@attribute"] = { link = "Constant" },
    ["@attribute.builtin"] = { fg = theme.syn.special1 },
    ["@property"] = { fg = theme.syn.identifier },

    -- Functions
    ["@function"] = { link = "Function" },
    ["@function.builtin"] = { fg = theme.syn.fun, italic = true },
    ["@function.call"] = { link = "Function" },
    ["@function.macro"] = { link = "Macro" },
    ["@function.method"] = { link = "Function" },
    ["@function.method.call"] = { link = "Function" },

    -- Constructors
    ["@constructor"] = { fg = theme.syn.special1 },
    ["@constructor.lua"] = { fg = theme.syn.keyword },

    -- Operators
    ["@operator"] = { link = "Operator" },

    -- Keywords
    ["@keyword"] = { link = "Keyword" },
    ["@keyword.coroutine"] = { fg = theme.syn.keyword, italic = true },
    ["@keyword.function"] = { fg = theme.syn.keyword },
    ["@keyword.operator"] = { fg = theme.syn.operator, bold = true },
    ["@keyword.import"] = { link = "PreProc" },
    ["@keyword.type"] = { link = "Type" },
    ["@keyword.modifier"] = { link = "StorageClass" },
    ["@keyword.repeat"] = { link = "Repeat" },
    ["@keyword.return"] = { fg = theme.syn.special3 },
    ["@keyword.debug"] = { link = "Debug" },
    ["@keyword.exception"] = { fg = theme.syn.special3 },
    ["@keyword.conditional"] = { link = "Conditional" },
    ["@keyword.conditional.ternary"] = { link = "Operator" },
    ["@keyword.directive"] = { link = "PreProc" },
    ["@keyword.directive.define"] = { link = "Define" },

    -- Punctuation
    ["@punctuation.delimiter"] = { fg = theme.syn.punct },
    ["@punctuation.bracket"] = { fg = theme.syn.punct },
    ["@punctuation.special"] = { fg = theme.syn.special1 },

    -- Comments
    ["@comment"] = { link = "Comment" },
    ["@comment.documentation"] = { fg = theme.syn.comment, italic = true },
    ["@comment.error"] = { fg = theme.ui.fg, bg = theme.diag.error, bold = true },
    ["@comment.warning"] = { fg = theme.ui.fg_reverse, bg = theme.diag.warning, bold = true },
    ["@comment.todo"] = { fg = theme.ui.fg_reverse, bg = theme.diag.hint, bold = true },
    ["@comment.note"] = { fg = theme.ui.fg_reverse, bg = theme.diag.info, bold = true },

    -- Markup
    ["@markup.strong"] = { bold = true },
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough"] = { strikethrough = true },
    ["@markup.underline"] = { underline = true },
    ["@markup.heading"] = { link = "Function" },
    ["@markup.quote"] = { fg = theme.syn.parameter, italic = true },
    ["@markup.math"] = { link = "Constant" },
    ["@markup.environment"] = { link = "Keyword" },
    ["@markup.link"] = { fg = theme.syn.special1 },
    ["@markup.link.label"] = { link = "Special" },
    ["@markup.link.url"] = { fg = theme.syn.special1, undercurl = true },
    ["@markup.raw"] = { link = "String" },
    ["@markup.raw.block"] = { fg = theme.syn.string },
    ["@markup.list"] = { fg = theme.syn.punct },
    ["@markup.list.checked"] = { fg = theme.diag.ok },
    ["@markup.list.unchecked"] = { fg = theme.ui.nontext },

    -- Diff
    ["@diff.plus"] = { fg = theme.vcs.added },
    ["@diff.minus"] = { fg = theme.vcs.removed },
    ["@diff.delta"] = { fg = theme.vcs.changed },

    -- Tags (HTML/XML)
    ["@tag"] = { link = "Tag" },
    ["@tag.builtin"] = { fg = theme.syn.special3 },
    ["@tag.attribute"] = { fg = theme.syn.identifier },
    ["@tag.delimiter"] = { fg = theme.syn.punct },
  }
end

return M
'''


def generate_lsp_lua() -> str:
    """Generate lsp.lua with semantic token highlights."""
    return '''-- Auto-generated LSP semantic highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- LSP semantic tokens
    ["@lsp.type.class"] = { link = "Structure" },
    ["@lsp.type.decorator"] = { link = "Function" },
    ["@lsp.type.enum"] = { link = "Structure" },
    ["@lsp.type.enumMember"] = { link = "Constant" },
    ["@lsp.type.function"] = { link = "Function" },
    ["@lsp.type.interface"] = { link = "Structure" },
    ["@lsp.type.macro"] = { link = "Macro" },
    ["@lsp.type.method"] = { link = "@function.method" },
    ["@lsp.type.namespace"] = { link = "@module" },
    ["@lsp.type.parameter"] = { link = "@variable.parameter" },
    ["@lsp.type.property"] = { link = "@property" },
    ["@lsp.type.struct"] = { link = "Structure" },
    ["@lsp.type.type"] = { link = "Type" },
    ["@lsp.type.typeParameter"] = { link = "Type" },
    ["@lsp.type.variable"] = { fg = "NONE" },
    ["@lsp.type.comment"] = { link = "Comment" },

    ["@lsp.type.const"] = { link = "Constant" },
    ["@lsp.type.comparison"] = { link = "Operator" },
    ["@lsp.type.bitwise"] = { link = "Operator" },
    ["@lsp.type.punctuation"] = { link = "Delimiter" },

    ["@lsp.type.selfParameter"] = { link = "@variable.builtin" },
    ["@lsp.type.builtinConstant"] = { link = "@constant.builtin" },
    ["@lsp.type.magicFunction"] = { link = "@function.builtin" },

    -- Modifiers
    ["@lsp.mod.readonly"] = { link = "Constant" },
    ["@lsp.mod.typeHint"] = { link = "Type" },
    ["@lsp.mod.defaultLibrary"] = { link = "Special" },
    ["@lsp.mod.builtin"] = { link = "Special" },

    -- Type + modifier combinations
    ["@lsp.typemod.operator.controlFlow"] = { link = "@keyword.exception" },
    ["@lsp.type.lifetime"] = { link = "Operator" },
    ["@lsp.typemod.keyword.documentation"] = { link = "Special" },
    ["@lsp.type.decorator.rust"] = { link = "PreProc" },

    ["@lsp.typemod.variable.global"] = { link = "Constant" },
    ["@lsp.typemod.variable.static"] = { link = "Constant" },
    ["@lsp.typemod.variable.defaultLibrary"] = { link = "Special" },

    ["@lsp.typemod.function.builtin"] = { link = "@function.builtin" },
    ["@lsp.typemod.function.defaultLibrary"] = { link = "@function.builtin" },
    ["@lsp.typemod.method.defaultLibrary"] = { link = "@function.builtin" },

    ["@lsp.typemod.variable.injected"] = { link = "@variable" },
    ["@lsp.typemod.function.readonly"] = { fg = theme.syn.fun, bold = true },
  }
end

return M
'''


def generate_plugins_lua() -> str:
    """Generate plugins.lua with plugin-specific highlights."""
    return '''-- Auto-generated plugin highlights
local M = {}

function M.setup(colors)
  local theme = colors.theme
  return {
    -- Gitsigns
    GitSignsAdd = { fg = theme.vcs.added, bg = theme.ui.bg_gutter },
    GitSignsChange = { fg = theme.vcs.changed, bg = theme.ui.bg_gutter },
    GitSignsDelete = { fg = theme.vcs.removed, bg = theme.ui.bg_gutter },

    -- Telescope
    TelescopeBorder = { fg = theme.ui.float.fg_border, bg = theme.ui.bg },
    TelescopeTitle = { fg = theme.ui.special },
    TelescopeSelection = { link = "CursorLine" },
    TelescopeSelectionCaret = { link = "CursorLineNr" },
    TelescopeResultsClass = { link = "Structure" },
    TelescopeResultsStruct = { link = "Structure" },
    TelescopeResultsField = { link = "@variable.member" },
    TelescopeResultsMethod = { link = "Function" },
    TelescopeResultsVariable = { link = "@variable" },
    TelescopePromptPrefix = { fg = theme.syn.fun },
    TelescopeMatching = { fg = theme.diag.warning, bold = true },

    -- blink.cmp
    BlinkCmpMenu = { link = "Pmenu" },
    BlinkCmpMenuSelection = { link = "PmenuSel" },
    BlinkCmpMenuBorder = { fg = theme.ui.bg_search, bg = theme.ui.pmenu.bg },
    BlinkCmpScrollBarThumb = { link = "PmenuThumb" },
    BlinkCmpScrollBarGutter = { link = "PmenuSbar" },
    BlinkCmpLabel = { fg = theme.ui.pmenu.fg },
    BlinkCmpLabelMatch = { fg = theme.syn.fun },
    BlinkCmpLabelDetails = { fg = theme.syn.comment },
    BlinkCmpLabelDeprecated = { fg = theme.syn.comment, strikethrough = true },
    BlinkCmpGhostText = { fg = theme.syn.comment },
    BlinkCmpDoc = { link = "NormalFloat" },
    BlinkCmpDocBorder = { link = "FloatBorder" },
    BlinkCmpDocCursorLine = { link = "Visual" },
    BlinkCmpSignatureHelp = { link = "NormalFloat" },
    BlinkCmpSignatureHelpBorder = { link = "FloatBorder" },
    BlinkCmpSignatureHelpActiveParameter = { link = "LspSignatureActiveParameter" },

    BlinkCmpKind = { fg = theme.ui.fg_dim },
    BlinkCmpKindText = { fg = theme.ui.fg },
    BlinkCmpKindMethod = { link = "@function.method" },
    BlinkCmpKindFunction = { link = "Function" },
    BlinkCmpKindConstructor = { link = "@constructor" },
    BlinkCmpKindField = { link = "@variable.member" },
    BlinkCmpKindVariable = { fg = theme.ui.fg_dim },
    BlinkCmpKindClass = { link = "Type" },
    BlinkCmpKindInterface = { link = "Type" },
    BlinkCmpKindModule = { link = "@module" },
    BlinkCmpKindProperty = { link = "@property" },
    BlinkCmpKindUnit = { link = "Number" },
    BlinkCmpKindValue = { link = "String" },
    BlinkCmpKindEnum = { link = "Type" },
    BlinkCmpKindKeyword = { link = "Keyword" },
    BlinkCmpKindSnippet = { link = "Special" },
    BlinkCmpKindColor = { link = "Special" },
    BlinkCmpKindFile = { link = "Directory" },
    BlinkCmpKindReference = { link = "Special" },
    BlinkCmpKindFolder = { link = "Directory" },
    BlinkCmpKindEnumMember = { link = "Constant" },
    BlinkCmpKindConstant = { link = "Constant" },
    BlinkCmpKindStruct = { link = "Type" },
    BlinkCmpKindEvent = { link = "Type" },
    BlinkCmpKindOperator = { link = "Operator" },
    BlinkCmpKindTypeParameter = { link = "Type" },
    BlinkCmpKindCopilot = { link = "String" },

    -- nvim-cmp (fallback)
    CmpDocumentation = { link = "NormalFloat" },
    CmpDocumentationBorder = { link = "FloatBorder" },
    CmpItemAbbr = { fg = theme.ui.pmenu.fg },
    CmpItemAbbrDeprecated = { fg = theme.syn.comment, strikethrough = true },
    CmpItemAbbrMatch = { fg = theme.syn.fun },
    CmpItemAbbrMatchFuzzy = { link = "CmpItemAbbrMatch" },
    CmpItemKindDefault = { fg = theme.ui.fg_dim },
    CmpItemMenu = { fg = theme.ui.fg_dim },
    CmpGhostText = { fg = theme.syn.comment },

    -- IndentBlankline
    IndentBlanklineChar = { fg = theme.ui.whitespace },
    IndentBlanklineSpaceChar = { fg = theme.ui.whitespace },
    IndentBlanklineSpaceCharBlankline = { fg = theme.ui.whitespace },
    IndentBlanklineContextChar = { fg = theme.ui.special },
    IndentBlanklineContextStart = { sp = theme.ui.special, underline = true },
    IblIndent = { fg = theme.ui.whitespace },
    IblWhitespace = { fg = theme.ui.whitespace },
    IblScope = { fg = theme.ui.special },

    -- Trouble
    TroubleIndent = { fg = theme.ui.whitespace },
    TroublePos = { fg = theme.ui.special },
    TroubleCount = { fg = theme.diag.warning, bold = true },
    TroubleNormal = { link = "Normal" },
    TroubleText = { fg = theme.ui.fg },
    TroubleSource = { fg = theme.syn.comment },
    TroubleFoldIcon = { fg = theme.ui.special },
    TroubleLocation = { fg = theme.ui.nontext },

    -- Todo-comments
    TodoBgFIX = { fg = theme.ui.bg, bg = theme.diag.error, bold = true },
    TodoBgHACK = { fg = theme.ui.bg, bg = theme.diag.warning, bold = true },
    TodoBgNOTE = { fg = theme.ui.bg, bg = theme.diag.info, bold = true },
    TodoBgPERF = { fg = theme.ui.bg, bg = theme.syn.special1, bold = true },
    TodoBgTODO = { fg = theme.ui.bg, bg = theme.diag.hint, bold = true },
    TodoBgWARN = { fg = theme.ui.bg, bg = theme.diag.warning, bold = true },
    TodoFgFIX = { fg = theme.diag.error },
    TodoFgHACK = { fg = theme.diag.warning },
    TodoFgNOTE = { fg = theme.diag.info },
    TodoFgPERF = { fg = theme.syn.special1 },
    TodoFgTODO = { fg = theme.diag.hint },
    TodoFgWARN = { fg = theme.diag.warning },

    -- Which-key
    WhichKey = { fg = theme.syn.fun },
    WhichKeyGroup = { fg = theme.syn.keyword },
    WhichKeyDesc = { fg = theme.ui.fg },
    WhichKeySeperator = { fg = theme.ui.nontext },
    WhichKeySeparator = { fg = theme.ui.nontext },
    WhichKeyFloat = { bg = theme.ui.bg_m1 },
    WhichKeyBorder = { link = "FloatBorder" },
    WhichKeyValue = { fg = theme.syn.comment },

    -- Noice
    NoiceCmdline = { fg = theme.ui.fg },
    NoiceCmdlineIcon = { fg = theme.syn.fun },
    NoiceCmdlineIconSearch = { fg = theme.diag.warning },
    NoiceCmdlinePopup = { link = "NormalFloat" },
    NoiceCmdlinePopupBorder = { link = "FloatBorder" },
    NoiceCmdlinePopupBorderSearch = { fg = theme.diag.warning },
    NoiceConfirm = { link = "NormalFloat" },
    NoiceConfirmBorder = { link = "FloatBorder" },
    NoiceFormatConfirm = { link = "CursorLine" },
    NoiceFormatConfirmDefault = { link = "Visual" },
    NoiceMini = { link = "MsgArea" },
    NoicePopup = { link = "NormalFloat" },
    NoicePopupBorder = { link = "FloatBorder" },
    NoicePopupmenu = { link = "Pmenu" },
    NoicePopupmenuBorder = { link = "FloatBorder" },
    NoicePopupmenuMatch = { fg = theme.syn.fun, bold = true },
    NoicePopupmenuSelected = { link = "PmenuSel" },
    NoiceScrollbar = { link = "PmenuSbar" },
    NoiceScrollbarThumb = { link = "PmenuThumb" },
    NoiceVirtualText = { fg = theme.diag.info },

    -- Oil
    OilDir = { link = "Directory" },
    OilDirIcon = { link = "Directory" },
    OilFile = { fg = theme.ui.fg },
    OilCreate = { fg = theme.vcs.added },
    OilDelete = { fg = theme.vcs.removed },
    OilMove = { fg = theme.vcs.changed },
    OilCopy = { fg = theme.diag.info },
    OilChange = { fg = theme.vcs.changed },
    OilRestore = { fg = theme.diag.hint },
    OilPurge = { fg = theme.diag.error },
    OilTrash = { fg = theme.diag.error },
    OilTrashSourcePath = { fg = theme.syn.comment },

    -- Bufferline
    BufferLineFill = { bg = theme.ui.bg_m3 },
    BufferLineBackground = { fg = theme.ui.nontext, bg = theme.ui.bg_m3 },
    BufferLineBuffer = { fg = theme.ui.nontext, bg = theme.ui.bg_m3 },
    BufferLineBufferSelected = { fg = theme.ui.fg, bg = theme.ui.bg, bold = true },
    BufferLineBufferVisible = { fg = theme.ui.fg_dim, bg = theme.ui.bg_m1 },
    BufferLineCloseButton = { fg = theme.ui.nontext, bg = theme.ui.bg_m3 },
    BufferLineCloseButtonSelected = { fg = theme.diag.error, bg = theme.ui.bg },
    BufferLineCloseButtonVisible = { fg = theme.ui.nontext, bg = theme.ui.bg_m1 },
    BufferLineIndicatorSelected = { fg = theme.syn.fun, bg = theme.ui.bg },
    BufferLineModified = { fg = theme.diag.warning, bg = theme.ui.bg_m3 },
    BufferLineModifiedSelected = { fg = theme.diag.warning, bg = theme.ui.bg },
    BufferLineModifiedVisible = { fg = theme.diag.warning, bg = theme.ui.bg_m1 },
    BufferLineSeparator = { fg = theme.ui.bg_m3, bg = theme.ui.bg_m3 },
    BufferLineSeparatorSelected = { fg = theme.ui.bg_m3, bg = theme.ui.bg },
    BufferLineSeparatorVisible = { fg = theme.ui.bg_m3, bg = theme.ui.bg_m1 },
    BufferLineTab = { fg = theme.ui.nontext, bg = theme.ui.bg_m3 },
    BufferLineTabSelected = { fg = theme.ui.fg, bg = theme.ui.bg, bold = true },
    BufferLineTabClose = { fg = theme.diag.error, bg = theme.ui.bg_m3 },

    -- DAP-UI
    DapUIScope = { link = "Special" },
    DapUIType = { link = "Type" },
    DapUIModifiedValue = { fg = theme.syn.special1, bold = true },
    DapUIDecoration = { fg = theme.ui.float.fg_border },
    DapUIThread = { fg = theme.syn.identifier },
    DapUIStoppedThread = { fg = theme.syn.special1 },
    DapUISource = { fg = theme.syn.special2 },
    DapUILineNumber = { fg = theme.syn.special1 },
    DapUIFloatBorder = { fg = theme.ui.float.fg_border },
    DapUIWatchesEmpty = { fg = theme.diag.error },
    DapUIWatchesValue = { fg = theme.syn.identifier },
    DapUIWatchesError = { fg = theme.diag.error },
    DapUIBreakpointsPath = { link = "Directory" },
    DapUIBreakpointsInfo = { fg = theme.diag.info },
    DapUIBreakpointsCurrentLine = { fg = theme.syn.identifier, bold = true },
    DapUIBreakpointsDisabledLine = { link = "Comment" },
    DapUIStepOver = { fg = theme.syn.special1 },
    DapUIStepInto = { fg = theme.syn.special1 },
    DapUIStepBack = { fg = theme.syn.special1 },
    DapUIStepOut = { fg = theme.syn.special1 },
    DapUIStop = { fg = theme.diag.error },
    DapUIPlayPause = { fg = theme.syn.string },
    DapUIRestart = { fg = theme.syn.string },
    DapUIUnavailable = { fg = theme.syn.comment },

    -- Diffview
    DiffviewFilePanelTitle = { fg = theme.syn.fun, bold = true },
    DiffviewFilePanelCounter = { fg = theme.syn.constant },
    DiffviewFilePanelFileName = { fg = theme.ui.fg },
    DiffviewFilePanelPath = { fg = theme.syn.comment },
    DiffviewFilePanelInsertions = { fg = theme.vcs.added },
    DiffviewFilePanelDeletions = { fg = theme.vcs.removed },
    DiffviewStatusAdded = { fg = theme.vcs.added },
    DiffviewStatusModified = { fg = theme.vcs.changed },
    DiffviewStatusRenamed = { fg = theme.vcs.changed },
    DiffviewStatusDeleted = { fg = theme.vcs.removed },
    DiffviewStatusUntracked = { fg = theme.diag.hint },

    -- Mini
    MiniCursorword = { underline = true },
    MiniCursorwordCurrent = { underline = true },
    MiniIndentscopeSymbol = { fg = theme.syn.special1 },
    MiniIndentscopePrefix = { nocombine = true },
    MiniJump = { link = "SpellRare" },
    MiniJump2dSpot = { fg = theme.syn.constant, bold = true, nocombine = true },
    MiniStatuslineDevinfo = { fg = theme.ui.fg_dim, bg = theme.ui.bg_p1 },
    MiniStatuslineFileinfo = { fg = theme.ui.fg_dim, bg = theme.ui.bg_p1 },
    MiniStatuslineFilename = { fg = theme.ui.fg_dim, bg = theme.ui.bg_dim },
    MiniStatuslineInactive = { link = "StatusLineNC" },
    MiniStatuslineModeCommand = { fg = theme.ui.bg, bg = theme.syn.operator, bold = true },
    MiniStatuslineModeInsert = { fg = theme.ui.bg, bg = theme.diag.ok, bold = true },
    MiniStatuslineModeNormal = { fg = theme.ui.bg_m3, bg = theme.syn.fun, bold = true },
    MiniStatuslineModeOther = { fg = theme.ui.bg, bg = theme.syn.type, bold = true },
    MiniStatuslineModeReplace = { fg = theme.ui.bg, bg = theme.syn.constant, bold = true },
    MiniStatuslineModeVisual = { fg = theme.ui.bg, bg = theme.syn.keyword, bold = true },
    MiniSurround = { link = "IncSearch" },
    MiniTrailspace = { bg = theme.vcs.removed },

    -- Lualine (via highlighting)
    LualineNormalA = { fg = theme.ui.bg, bg = theme.syn.fun, bold = true },
    LualineNormalB = { fg = theme.ui.fg, bg = theme.ui.bg_p1 },
    LualineNormalC = { fg = theme.ui.fg_dim, bg = theme.ui.bg_m3 },
    LualineInsertA = { fg = theme.ui.bg, bg = theme.diag.ok, bold = true },
    LualineVisualA = { fg = theme.ui.bg, bg = theme.syn.keyword, bold = true },
    LualineReplaceA = { fg = theme.ui.bg, bg = theme.diag.error, bold = true },
    LualineCommandA = { fg = theme.ui.bg, bg = theme.diag.warning, bold = true },

    -- Lazy
    LazyProgressTodo = { fg = theme.ui.nontext },
    LazyProgressDone = { fg = theme.diag.ok },

    -- Notify
    NotifyBackground = { bg = theme.ui.bg },
    NotifyERRORBorder = { link = "DiagnosticError" },
    NotifyWARNBorder = { link = "DiagnosticWarn" },
    NotifyINFOBorder = { link = "DiagnosticInfo" },
    NotifyHINTBorder = { link = "DiagnosticHint" },
    NotifyDEBUGBorder = { link = "Debug" },
    NotifyTRACEBorder = { link = "Comment" },
    NotifyERRORIcon = { link = "DiagnosticError" },
    NotifyWARNIcon = { link = "DiagnosticWarn" },
    NotifyINFOIcon = { link = "DiagnosticInfo" },
    NotifyHINTIcon = { link = "DiagnosticHint" },
    NotifyDEBUGIcon = { link = "Debug" },
    NotifyTRACEIcon = { link = "Comment" },
    NotifyERRORTitle = { link = "DiagnosticError" },
    NotifyWARNTitle = { link = "DiagnosticWarn" },
    NotifyINFOTitle = { link = "DiagnosticInfo" },
    NotifyHINTTitle = { link = "DiagnosticHint" },
    NotifyDEBUGTitle = { link = "Debug" },
    NotifyTRACETitle = { link = "Comment" },

    -- TreesitterContext
    TreesitterContext = { link = "Folded" },
    TreesitterContextLineNumber = { fg = theme.ui.special, bg = theme.ui.bg_gutter },

    -- Render-markdown
    RenderMarkdownH1Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownH2Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownH3Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownH4Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownH5Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownH6Bg = { bg = theme.ui.bg_p1 },
    RenderMarkdownCode = { bg = theme.ui.bg_p1 },
    RenderMarkdownCodeInline = { bg = theme.ui.bg_p1 },
    RenderMarkdownBullet = { fg = theme.syn.fun },
    RenderMarkdownQuote = { fg = theme.syn.comment, italic = true },
    RenderMarkdownDash = { fg = theme.ui.nontext },
    RenderMarkdownLink = { fg = theme.syn.special1 },
    RenderMarkdownSign = { fg = theme.ui.special },
    RenderMarkdownMath = { fg = theme.syn.constant },
    RenderMarkdownUnchecked = { fg = theme.ui.nontext },
    RenderMarkdownChecked = { fg = theme.diag.ok },
    RenderMarkdownTableHead = { fg = theme.syn.fun },
    RenderMarkdownTableRow = { fg = theme.ui.fg },
    RenderMarkdownTableFill = { link = "Conceal" },

    -- Copilot
    CopilotSuggestion = { fg = theme.syn.comment, italic = true },
    CopilotAnnotation = { fg = theme.syn.comment, italic = true },

    -- CodeCompanion
    CodeCompanionChatHeader = { fg = theme.syn.fun, bold = true },
    CodeCompanionChatSeparator = { fg = theme.ui.nontext },
    CodeCompanionChatTokens = { fg = theme.syn.comment },
    CodeCompanionChatAgent = { fg = theme.syn.special1 },
    CodeCompanionChatTool = { fg = theme.syn.keyword },
    CodeCompanionChatVariable = { fg = theme.syn.constant },
    CodeCompanionVirtualText = { fg = theme.syn.comment, italic = true },

    -- Fidget
    FidgetTitle = { fg = theme.syn.fun },
    FidgetTask = { fg = theme.syn.comment },

    -- Health
    healthError = { fg = theme.diag.error },
    healthSuccess = { fg = theme.diag.ok },
    healthWarning = { fg = theme.diag.warning },
  }
end

return M
'''


def generate_init_lua(module_name: str, theme_name: str, colorscheme_name: str) -> str:
    """Generate init.lua entry point."""
    return f'''-- Auto-generated colorscheme: {theme_name}
local M = {{}}

M.config = {{
  transparent = false,
  dim_inactive = false,
  terminal_colors = true,
}}

function M.setup(opts)
  M.config = vim.tbl_deep_extend("force", M.config, opts or {{}})
end

function M.load()
  if vim.g.colors_name then
    vim.cmd("hi clear")
  end

  vim.g.colors_name = "{colorscheme_name}"
  vim.o.termguicolors = true
  vim.o.background = "dark"

  local colors = require("{module_name}.palette")
  local highlights = {{}}

  -- Collect all highlight groups
  for _, mod in ipairs({{ "editor", "syntax", "treesitter", "lsp", "plugins" }}) do
    local ok, hl_mod = pcall(require, "{module_name}.highlights." .. mod)
    if ok then
      for hl, spec in pairs(hl_mod.setup(colors)) do
        highlights[hl] = spec
      end
    end
  end

  -- Apply highlights
  for hl, spec in pairs(highlights) do
    vim.api.nvim_set_hl(0, hl, spec)
  end

  -- Terminal colors
  if M.config.terminal_colors then
    local p = colors.palette
    vim.g.terminal_color_0 = p.base00
    vim.g.terminal_color_1 = p.base08
    vim.g.terminal_color_2 = p.base0B
    vim.g.terminal_color_3 = p.base0A
    vim.g.terminal_color_4 = p.base0D
    vim.g.terminal_color_5 = p.base0E
    vim.g.terminal_color_6 = p.base0C
    vim.g.terminal_color_7 = p.base05
    vim.g.terminal_color_8 = p.base03
    vim.g.terminal_color_9 = p.base08
    vim.g.terminal_color_10 = p.base0B
    vim.g.terminal_color_11 = p.base0A
    vim.g.terminal_color_12 = p.base0D
    vim.g.terminal_color_13 = p.base0E
    vim.g.terminal_color_14 = p.base0C
    vim.g.terminal_color_15 = p.base07
  end
end

return M
'''


def generate_highlights_init_lua(module_name: str) -> str:
    """Generate highlights/init.lua."""
    return f'''-- Auto-generated highlights init
local M = {{}}

function M.setup(colors)
  local highlights = {{}}

  for _, mod in ipairs({{ "editor", "syntax", "treesitter", "lsp", "plugins" }}) do
    local ok, hl_mod = pcall(require, "{module_name}.highlights." .. mod)
    if ok then
      for hl, spec in pairs(hl_mod.setup(colors)) do
        highlights[hl] = spec
      end
    end
  end

  return highlights
end

return M
'''


def generate_colors_lua(module_name: str) -> str:
    """Generate colors/{name}.lua entry point."""
    return f'''-- Colorscheme entry point
require("{module_name}").load()
'''


def generate_colorscheme(theme_path: Path, output_dir: Path) -> None:
    """Generate complete Neovim colorscheme from theme.yml."""
    theme = load_theme(theme_path)
    meta = theme.get("meta", {})
    slug = meta.get("id", theme_path.parent.name)
    name = meta.get("display_name", slug)
    module_name = slug_to_module(slug)

    # Create directory structure
    lua_dir = output_dir / "lua" / module_name
    highlights_dir = lua_dir / "highlights"
    colors_dir = output_dir / "colors"

    for d in [lua_dir, highlights_dir, colors_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Generate files
    files = {
        lua_dir / "init.lua": generate_init_lua(module_name, name, slug),
        lua_dir / "palette.lua": generate_palette_lua(theme),
        highlights_dir / "init.lua": generate_highlights_init_lua(module_name),
        highlights_dir / "editor.lua": generate_editor_lua(),
        highlights_dir / "syntax.lua": generate_syntax_lua(),
        highlights_dir / "treesitter.lua": generate_treesitter_lua(),
        highlights_dir / "lsp.lua": generate_lsp_lua(),
        highlights_dir / "plugins.lua": generate_plugins_lua(),
        colors_dir / f"{slug}.lua": generate_colors_lua(module_name),
    }

    for filepath, content in files.items():
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  Created: {filepath.relative_to(output_dir)}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: neovim_generator.py <theme_dir>")
        print("  theme_dir: Directory containing theme.yml")
        sys.exit(1)

    theme_dir = Path(sys.argv[1])
    theme_path = theme_dir / "theme.yml"

    if not theme_path.exists():
        print(f"Error: {theme_path} not found")
        sys.exit(1)

    output_dir = theme_dir / "neovim"
    print(f"Generating Neovim colorscheme from: {theme_path}")
    print(f"Output directory: {output_dir}")

    generate_colorscheme(theme_path, output_dir)
    print("Done!")


if __name__ == "__main__":
    main()
