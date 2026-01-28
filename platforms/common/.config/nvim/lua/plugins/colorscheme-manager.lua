-- Unified Colorscheme Manager
-- Handles colorscheme plugins, persistence, and git-based loading

return {
  {
    'projekt0n/github-nvim-theme',
    name = 'github-theme',
    lazy = false,
    priority = 1000,
    config = function()
      require('github-theme').setup()
    end,
  },
  {
    'rose-pine/neovim',
    name = 'rose-pine',
    lazy = false,
    config = function()
      require('rose-pine').setup({
        variant = 'auto',
        dark_variant = 'main',
      })
    end,
  },
  { 'rebelot/kanagawa.nvim', lazy = false },
  { 'ellisonleao/gruvbox.nvim', lazy = false },
  { 'AlexvZyl/nordic.nvim', lazy = false },
  { 'EdenEast/nightfox.nvim', lazy = false },
  { 'craftzdog/solarized-osaka.nvim', lazy = false },
  { 'mhartington/oceanic-next', lazy = false },
  { 'datapointchris/flexoki-moon-nvim', lazy = false },
  {
    'neanias/everforest-nvim',
    version = false,
    lazy = false,
    priority = 1000,
    config = function()
      vim.o.background = 'dark'
      require('everforest').setup({
        background = 'hard',
        colours_override = function(palette)
          palette.bg0 = palette.bg_dim
        end,
      })
    end,
  },

  -- Generated themes from theme system (~/tools/theme)
  -- Dynamically load all themes that have a neovim/ directory
  (function()
    local themes_dir = vim.fn.expand('~/tools/theme/themes')
    local generated_themes = {}
    local handle = vim.loop.fs_scandir(themes_dir)
    if handle then
      while true do
        local name, type = vim.loop.fs_scandir_next(handle)
        if not name then
          break
        end
        if type == 'directory' then
          local neovim_dir = themes_dir .. '/' .. name .. '/neovim'
          if vim.fn.isdirectory(neovim_dir) == 1 then
            table.insert(generated_themes, {
              dir = neovim_dir,
              name = name,
              lazy = false,
              cond = function()
                return require('core.profiles').is_full
              end,
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
      local themes_dir = vim.fn.expand('~/tools/theme/themes')
      local history_file = vim.fn.expand('~/.local/state/theme/history.jsonl')

      -- Configuration
      local config = {
        per_repo_persistence = false, -- Use theme system instead of per-repo colorschemes
      }

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
        if vim.fn.filereadable(history_file) == 0 then
          return rejected
        end

        local lines = vim.fn.readfile(history_file)
        local last_action = {} -- theme -> {action, ts}

        for _, line in ipairs(lines) do
          if line ~= '' then
            local ok, entry = pcall(vim.json.decode, line)
            if ok and entry and entry.theme then
              local action = entry.action
              if action == 'reject' or action == 'unreject' then
                last_action[entry.theme] = action
              end
            end
          end
        end

        for theme, action in pairs(last_action) do
          if action == 'reject' then
            rejected[theme] = true
          end
        end

        return rejected
      end

      -- Parse meta fields from theme.yml (simple pattern matching)
      local function parse_theme_yml(theme_path)
        local yml_path = theme_path .. '/theme.yml'
        if vim.fn.filereadable(yml_path) == 0 then
          return nil
        end
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
          if key and value then
            result[key] = value
          end
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
        if not handle then
          return display_map
        end

        while true do
          local name, type = vim.loop.fs_scandir_next(handle)
          if not name then
            break
          end
          if type == 'directory' then
            local meta = parse_theme_yml(themes_dir .. '/' .. name)
            if meta and meta.neovim_colorscheme_name then
              local display_name = meta.display_name or name
              local source = meta.neovim_colorscheme_source or ''
              local source_label = ''
              if source == 'generated' then
                source_label = ' (Generated)'
              elseif source == 'plugin' then
                source_label = ' (Neovim Plugin)'
              end
              display_map[meta.neovim_colorscheme_name] = display_name .. source_label
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
        if not handle then
          return colorschemes
        end

        while true do
          local name, type = vim.loop.fs_scandir_next(handle)
          if not name then
            break
          end
          if type == 'directory' and not rejected[name] then
            local theme_path = themes_dir .. '/' .. name
            local neovim_dir = theme_path .. '/neovim'
            local meta = parse_theme_yml(theme_path)

            -- Include if has neovim/ dir (generated) OR neovim_colorscheme_source is 'plugin'
            local has_neovim_dir = vim.fn.isdirectory(neovim_dir) == 1
            local is_plugin_theme = meta and meta.neovim_colorscheme_source == 'plugin'

            if has_neovim_dir or is_plugin_theme then
              local colorscheme = meta and meta.neovim_colorscheme_name
              if colorscheme then
                table.insert(colorschemes, colorscheme)
              end
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
        if #all_colorschemes == 0 then
          return 'default'
        end
        math.randomseed(os.time())
        local index = math.random(#all_colorschemes)
        return all_colorschemes[index]
      end

      -- === THEME SYSTEM INTEGRATION ===
      local theme_current_file = vim.fn.expand('~/.local/state/theme/current')

      local function get_current_theme_from_system()
        if vim.fn.filereadable(theme_current_file) == 0 then
          return nil
        end
        local lines = vim.fn.readfile(theme_current_file)
        if #lines > 0 and lines[1] ~= '' then
          return lines[1]
        end
        return nil
      end

      local function load_colorscheme_from_theme_system()
        local theme_name = get_current_theme_from_system()
        if not theme_name then
          return false
        end

        local meta = parse_theme_yml(themes_dir .. '/' .. theme_name)
        local colorscheme = meta and meta.neovim_colorscheme_name
        if not colorscheme then
          return false
        end

        -- Ensure dark background for dark variant themes
        if meta.variant == 'dark' then
          vim.o.background = 'dark'
        elseif meta.variant == 'light' then
          vim.o.background = 'light'
        end

        local ok = pcall(vim.cmd, 'colorscheme ' .. colorscheme)
        if ok then
          require('fidget').notify('Theme: ' .. colorscheme)
        end
        return ok
      end

      local function setup_theme_file_watcher()
        local w = vim.loop.new_fs_event()
        if not w then
          return
        end

        local theme_dir = vim.fn.expand('~/.local/state/theme')
        w:start(theme_dir, {}, function(err, filename)
          if err then
            return
          end
          if filename == 'current' then
            vim.schedule(function()
              load_colorscheme_from_theme_system()
            end)
          end
        end)
      end

      -- === GIT-BASED PERSISTENCE ===
      local data_path = vim.fn.stdpath('data') .. '/git_colorschemes'
      local function ensure_data_dir()
        vim.fn.mkdir(data_path, 'p')
      end
      local function find_git_root()
        local current_dir = vim.fn.getcwd()
        local git_dir = vim.fn.finddir('.git', current_dir .. ';')

        if git_dir ~= '' then
          local git_root = vim.fn.fnamemodify(git_dir, ':h')
          -- Convert relative path to absolute path
          if git_root == '.' then
            git_root = current_dir
          elseif not vim.startswith(git_root, '/') then
            git_root = vim.fn.fnamemodify(git_root, ':p'):gsub('/$', '')
          end
          return git_root
        end

        return nil
      end

      local function repo_to_safe_filename(repo_path)
        local filename = repo_path:gsub('/', '_'):gsub('^_', '')
        return data_path .. '/' .. filename
      end

      local function get_project_name_from_repo_path(repo_path)
        local project_name = vim.fn.fnamemodify(repo_path, ':t')
        if project_name == '' or project_name == '.' then
          local parts = vim.split(repo_path, '/', { plain = true })
          project_name = parts[#parts] or 'unknown'
        end
        return project_name
      end

      local function save_colorscheme()
        local git_root = find_git_root()
        if not git_root then
          return
        end

        local current_colorscheme = vim.g.colors_name
        if current_colorscheme then
          ensure_data_dir()
          local file_path = repo_to_safe_filename(git_root)
          local file = io.open(file_path, 'w')
          if file then
            file:write(current_colorscheme)
            file:close()
          end
        end
      end

      local function load_colorscheme()
        local git_root = find_git_root()

        if git_root then
          local file_path = repo_to_safe_filename(git_root)
          local file = io.open(file_path, 'r')
          if file then
            local colorscheme = file:read('*line')
            file:close()
            if colorscheme and colorscheme ~= '' then
              vim.cmd('colorscheme ' .. colorscheme)

              -- Send notification via fidget
              local project_name = get_project_name_from_repo_path(git_root)
              require('fidget').notify('Loaded colorscheme "' .. colorscheme .. '" from ' .. project_name .. ' project')
              return true
            end
          end

          -- In git repo but no saved colorscheme, use random
          local random_colorscheme = get_random_colorscheme()
          vim.cmd('colorscheme ' .. random_colorscheme)

          local project_name = get_project_name_from_repo_path(git_root)
          require('fidget').notify('Loaded random colorscheme "' .. random_colorscheme .. '" for ' .. project_name .. ' project')
          return true
        else
          -- Not in a git repository, use random colorscheme
          local random_colorscheme = get_random_colorscheme()
          vim.cmd('colorscheme ' .. random_colorscheme)

          require('fidget').notify('Loaded random colorscheme "' .. random_colorscheme .. '"')
          return true
        end
      end

      -- Setup autocmds for persistence
      local function setup_auto_save()
        vim.api.nvim_create_autocmd('ColorScheme', {
          group = vim.api.nvim_create_augroup('GitColorschemePersiestence', { clear = true }),
          callback = function()
            save_colorscheme()
          end,
        })

        -- Auto-load when changing directories
        vim.api.nvim_create_autocmd('DirChanged', {
          group = vim.api.nvim_create_augroup('GitColorschemePersiestenceDirChange', { clear = true }),
          callback = function()
            load_colorscheme()
          end,
        })
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

      if config.per_repo_persistence then
        -- Use per-repo colorscheme persistence
        if not load_colorscheme() then
          vim.cmd('colorscheme github_dark_dimmed')
        end
        setup_auto_save()
      else
        -- Use theme system integration
        if not load_colorscheme_from_theme_system() then
          local random_cs = get_random_colorscheme()
          pcall(vim.cmd, 'colorscheme ' .. random_cs)
        end
        setup_theme_file_watcher()
      end
    end,
  },
}
