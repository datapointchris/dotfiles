-- Unified Colorscheme Manager
-- Handles colorscheme plugins, persistence, and git-based loading

-- Colorscheme plugins are lazy-loaded on demand: lazy.nvim's ColorSchemePre
-- autocmd loads whichever plugin provides `colors/<name>.{lua,vim}` the moment
-- `:colorscheme <name>` runs, so only the active theme is ever loaded. The
-- colorscheme-manager below (kept eager) drives that selection at startup and
-- via the theme-tool file watcher.

local themes_dir = vim.fn.expand('~/.local/share/theme/themes')

-- The colorscheme a theme's generated tree provides, read off disk rather than
-- rebuilt from theme.yml.
--
-- The name is not the theme id: a theme whose colours come from a plugin gets a
-- `theme-` prefix, because most of those ids are the plugin's own colorscheme
-- name and two colors/kanagawa.lua on the runtimepath is a coin toss. That rule
-- belongs to the generator, and reading the filename means it can change there
-- without this file learning about it.
local function generated_colorscheme(theme)
  local colors_dir = themes_dir .. '/' .. theme .. '/neovim/colors'
  local handle = vim.loop.fs_scandir(colors_dir)
  if not handle then return nil end

  while true do
    local name, type = vim.loop.fs_scandir_next(handle)
    if not name then return nil end
    if type == 'file' and name:sub(-4) == '.lua' then return name:sub(1, -5) end
  end
end

return {
  -- Colorscheme plugins, read out of the theme library rather than listed here.
  --
  -- Every theme.yml already names the repo its colorscheme comes from, so a copy
  -- of that list in this file was a second place to forget — and forgetting is
  -- silent: :colorscheme finds nothing and the apply leaves the previous theme up
  -- with no error. Only the setup options below are knowledge theme.yml does not
  -- carry; everything else is derived.
  (function()
    -- Plugins whose look is a setup call rather than a colorscheme name.
    local options = {
      ['projekt0n/github-nvim-theme'] = {
        name = 'github-theme',
        config = function() require('github-theme').setup() end,
      },
      ['rose-pine/neovim'] = {
        name = 'rose-pine',
        config = function()
          require('rose-pine').setup({
            variant = 'auto',
            dark_variant = 'main',
          })
        end,
      },
      ['neanias/everforest-nvim'] = {
        version = false,
        config = function()
          vim.o.background = 'dark'
          require('everforest').setup({
            background = 'hard',
            colours_override = function(palette) palette.bg0 = palette.bg_dim end,
          })
        end,
      },
    }

    -- Quoted first, then bare: one theme.yml writes the repo unquoted, and a
    -- quoted-only match would drop it — which is everforest, one of the three
    -- that needs its options above.
    local function plugin_repo(line)
      local repo = line:match('^%s*plugin:%s*"([^"]+)"') or line:match("^%s*plugin:%s*'([^']+)'")
      if repo then return repo end
      local bare = line:match('^%s*plugin:%s*([^%s#]+)')
      if bare and bare ~= 'null' and bare ~= '~' then return bare end
      return nil
    end

    local specs, seen = {}, {}
    local handle = vim.loop.fs_scandir(themes_dir)
    if not handle then return specs end

    while true do
      local name, type = vim.loop.fs_scandir_next(handle)
      if not name then break end
      if type == 'directory' then
        local yml = themes_dir .. '/' .. name .. '/theme.yml'
        if vim.fn.filereadable(yml) == 1 then
          for _, line in ipairs(vim.fn.readfile(yml)) do
            local repo = plugin_repo(line)
            -- Several themes share one plugin — cendre has three depths and
            -- flexoki-moon four variants — so the spec is emitted once.
            if repo and not seen[repo] then
              seen[repo] = true
              table.insert(specs, vim.tbl_extend('force', { repo, lazy = true }, options[repo] or {}))
            end
          end
        end
      end
    end

    return specs
  end)(),

  -- Generated colorschemes from the theme tool (~/.local/share/theme).
  --
  -- Every theme ships one. For a theme with no upstream plugin it is the
  -- colorscheme; for the rest it is the fallback the manager reaches for when
  -- the plugin is not on this machine.
  (function()
    local generated_themes = {}
    local handle = vim.loop.fs_scandir(themes_dir)
    if handle then
      while true do
        local name, type = vim.loop.fs_scandir_next(handle)
        if not name then break end
        if type == 'directory' then
          local colorscheme = generated_colorscheme(name)
          -- Named after the colorscheme, not the theme directory. lazy.nvim
          -- errors on two plugins sharing a name, and the rose-pine theme
          -- directory collides with the rose-pine plugin's own spec.
          if colorscheme then
            table.insert(generated_themes, {
              dir = themes_dir .. '/' .. name .. '/neovim',
              name = colorscheme,
              lazy = true,
              cond = function() return require('core.profiles').is_full end,
            })
          end
        end
      end
    end
    return generated_themes
  end)(),

  -- === COLORSCHEME MANAGER ===
  {
    'colorscheme-manager',
    dir = vim.fn.stdpath('config') .. '/lua/plugins', -- Dummy dir since this is embedded
    name = 'colorscheme-manager',
    lazy = false,
    priority = 999, -- Load after colorscheme plugins but before other plugins
    config = function()
      local history_file = vim.fn.expand('~/.local/state/theme/history.jsonl')

      -- Manually curated plugin colorschemes (plugins expose variants, only include good ones)
      local good_plugin_colorschemes = {
        'everforest',
        'terafox',
        'solarized-osaka',
        'slate',
        'retrobox',
        'carbonfox',
        'OceanicNext',
        'nordic',
        'nightfox',
        'kanagawa',
        'gruvbox',
        'rose-pine',
        'github_dark_default',
        'github_dark_dimmed',
        'flexoki-moon-toddler',
        'flexoki-moon-red',
        'flexoki-moon-purple',
        'flexoki-moon-green',
        'flexoki-moon-black',
      }

      -- Load rejected themes from history.jsonl
      -- A theme is rejected if its last reject/unreject action was "reject"
      local function get_rejected_themes()
        local rejected = {}
        if vim.fn.filereadable(history_file) == 0 then return rejected end

        local lines = vim.fn.readfile(history_file)
        local last_action = {} -- theme -> {action, ts}

        for _, line in ipairs(lines) do
          if line ~= '' then
            local ok, entry = pcall(vim.json.decode, line)
            if ok and entry and entry.theme then
              local action = entry.action
              if action == 'reject' or action == 'unreject' then last_action[entry.theme] = action end
            end
          end
        end

        for theme, action in pairs(last_action) do
          if action == 'reject' then rejected[theme] = true end
        end

        return rejected
      end

      -- Parse meta fields from theme.yml (simple pattern matching)
      local function parse_theme_yml(theme_path)
        local yml_path = theme_path .. '/theme.yml'
        if vim.fn.filereadable(yml_path) == 0 then return nil end
        local lines = vim.fn.readfile(yml_path)
        local result = {}
        for _, line in ipairs(lines) do
          -- Try quoted value first (handles spaces), then unquoted
          local key, value = line:match('^%s*([%w_]+):%s*"([^"]*)"')
          if not key then
            key, value = line:match("^%s*([%w_]+):%s*'([^']*)'")
          end
          if not key then
            key, value = line:match('^%s*([%w_]+):%s*([^%s#]+)')
          end
          if key and value then result[key] = value end
        end
        return result
      end

      local function get_neovim_colorscheme_from_yml(theme_path)
        local meta = parse_theme_yml(theme_path)
        return meta and meta.neovim_colorscheme_name or nil
      end

      -- Build display name mapping for all themes
      local function build_colorscheme_display_map()
        local display_map = {}
        local handle = vim.loop.fs_scandir(themes_dir)
        if not handle then return display_map end

        while true do
          local name, type = vim.loop.fs_scandir_next(handle)
          if not name then break end
          if type == 'directory' then
            local meta = parse_theme_yml(themes_dir .. '/' .. name)
            if meta and meta.neovim_colorscheme_name then
              local colorscheme = meta.neovim_colorscheme_name
              -- Several themes can share one colorscheme name when the plugin
              -- exposes its variants as setup options (cendre's three depths).
              -- The picker only ever shows one entry for them, so label it from
              -- the theme whose id is the bare colorscheme name rather than from
              -- whichever directory scandir happened to reach last.
              local is_collision = display_map[colorscheme] ~= nil
              if not is_collision or meta.id == colorscheme then
                local display_name = meta.display_name or name
                local source = meta.neovim_colorscheme_source or ''
                local source_label = ''
                if source == 'generated' then
                  source_label = ' (Generated)'
                elseif source == 'plugin' then
                  source_label = ' (Neovim Plugin)'
                end
                display_map[colorscheme] = display_name .. source_label
              end
            end
          end
        end

        return display_map
      end

      -- Dynamically get system colorschemes from theme system
      local function get_system_colorschemes()
        local colorschemes = {}
        local rejected = get_rejected_themes()

        local handle = vim.loop.fs_scandir(themes_dir)
        if not handle then return colorschemes end

        while true do
          local name, type = vim.loop.fs_scandir_next(handle)
          if not name then break end
          if type == 'directory' and not rejected[name] then
            local theme_path = themes_dir .. '/' .. name
            local neovim_dir = theme_path .. '/neovim'
            local meta = parse_theme_yml(theme_path)

            -- Include if has neovim/ dir (generated) OR neovim_colorscheme_source is 'plugin'
            local has_neovim_dir = vim.fn.isdirectory(neovim_dir) == 1
            local is_plugin_theme = meta and meta.neovim_colorscheme_source == 'plugin'

            if has_neovim_dir or is_plugin_theme then
              local colorscheme = meta and meta.neovim_colorscheme_name
              if colorscheme then table.insert(colorschemes, colorscheme) end
            end
          end
        end

        return colorschemes
      end

      -- Merge plugin and system colorschemes, removing duplicates and rejected
      local function get_all_good_colorschemes()
        local all = {}
        local seen = {}
        local rejected = get_rejected_themes()

        for _, cs in ipairs(good_plugin_colorschemes) do
          if not seen[cs] and not rejected[cs] then
            table.insert(all, cs)
            seen[cs] = true
          end
        end

        for _, cs in ipairs(get_system_colorschemes()) do
          if not seen[cs] then
            table.insert(all, cs)
            seen[cs] = true
          end
        end

        return all
      end

      local function get_random_colorscheme()
        local all_colorschemes = get_all_good_colorschemes()
        if #all_colorschemes == 0 then return 'default' end
        math.randomseed(os.time())
        local index = math.random(#all_colorschemes)
        return all_colorschemes[index]
      end

      -- === THEME SYSTEM INTEGRATION ===
      local theme_current_file = vim.fn.expand('~/.local/state/theme/current')

      local function get_current_theme_from_system()
        if vim.fn.filereadable(theme_current_file) == 0 then return nil end
        local lines = vim.fn.readfile(theme_current_file)
        if #lines > 0 and lines[1] ~= '' then return lines[1] end
        return nil
      end

      local function load_colorscheme_from_theme_system()
        local theme_name = get_current_theme_from_system()
        if not theme_name then return false end

        local meta = parse_theme_yml(themes_dir .. '/' .. theme_name)
        local colorscheme = meta and meta.neovim_colorscheme_name
        if not colorscheme then return false end

        -- Ensure dark background for dark variant themes
        if meta.variant == 'dark' then
          vim.o.background = 'dark'
        elseif meta.variant == 'light' then
          vim.o.background = 'light'
        end

        -- Some plugins expose a variant as a setup option rather than as its own
        -- colorscheme name, so the variant has to be selected before the
        -- colorscheme loads or Neovim keeps the plugin default while every other
        -- app moves. The module is assumed to be named after the colorscheme,
        -- which holds for every plugin using this key so far.
        if meta.neovim_plugin_background then
          local configured, err = pcall(function() require(colorscheme).setup({ background = meta.neovim_plugin_background }) end)
          if not configured then
            vim.notify('colorscheme-manager: could not set ' .. colorscheme .. ' background: ' .. tostring(err), vim.log.levels.WARN)
          end
        end

        local ok, err = pcall(vim.cmd, 'colorscheme ' .. colorscheme)
        if ok then
          require('fidget').notify('Theme: ' .. colorscheme)
          return true
        end

        -- The plugin is not on this machine — never synced, no network, or a
        -- locked-down box. Every theme ships a colorscheme generated from its
        -- own palette for exactly this, so the editor moves with the terminal
        -- instead of silently keeping the previous theme.
        --
        -- Loudly, though. A generated colorscheme is derived from the palette
        -- where the plugin was tuned by hand, so it is close rather than right,
        -- and a fallback nobody is told about is indistinguishable from the
        -- theme having applied.
        local fallback = generated_colorscheme(theme_name)
        if fallback and fallback ~= colorscheme then
          local fell_back = pcall(vim.cmd, 'colorscheme ' .. fallback)
          if fell_back then
            vim.notify(
              'colorscheme-manager: '
                .. colorscheme
                .. ' is not installed — using '
                .. fallback
                .. ', generated from this palette rather than tuned by the theme author.',
              vim.log.levels.WARN
            )
            return true
          end
        end

        vim.notify(
          'colorscheme-manager: ' .. colorscheme .. ' failed to load and has no usable fallback: ' .. tostring(err),
          vim.log.levels.WARN
        )
        return false
      end

      local function setup_theme_file_watcher()
        local w = vim.loop.new_fs_event()
        if not w then return end

        local theme_dir = vim.fn.expand('~/.local/state/theme')
        w:start(theme_dir, {}, function(err, filename)
          if err then return end
          if filename == 'current' then vim.schedule(function() load_colorscheme_from_theme_system() end) end
        end)
      end

      -- For Telescope to be able to pick from the good colorschemes
      _G.ColorschemeManager = {
        good_colorschemes = get_all_good_colorschemes(),
        good_plugin_colorschemes = good_plugin_colorschemes,
        get_system_colorschemes = get_system_colorschemes,
        get_all_good_colorschemes = get_all_good_colorschemes,
        get_random_colorscheme = get_random_colorscheme,
        load_from_theme_system = load_colorscheme_from_theme_system,
        display_map = build_colorscheme_display_map(),
      }

      -- Apply the theme tool's current selection at startup, then watch the
      -- theme state file so external `theme` changes update Neovim live.
      if not load_colorscheme_from_theme_system() then
        local random_cs = get_random_colorscheme()
        pcall(vim.cmd, 'colorscheme ' .. random_cs)
      end
      setup_theme_file_watcher()
    end,
  },
}
