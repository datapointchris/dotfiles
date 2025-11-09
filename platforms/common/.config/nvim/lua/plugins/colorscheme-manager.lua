-- Unified Colorscheme Manager
-- Handles colorscheme plugins, persistence, and git-based loading

return {
  {
    'projekt0n/github-nvim-theme',
    name = 'github-theme',
    lazy = false,
    priority = 1000,
    cond = not vim.g.vscode,
    config = function() require('github-theme').setup() end,
  },
  {
    'rose-pine/neovim',
    name = 'rose-pine',
    lazy = false,
    cond = not vim.g.vscode,
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

  -- === COLORSCHEME MANAGER ===
  {
    'colorscheme-manager',
    dir = vim.fn.stdpath('config') .. '/lua/plugins', -- Dummy dir since this is embedded
    name = 'colorscheme-manager',
    lazy = false,
    priority = 999, -- Load after colorscheme plugins but before other plugins
    cond = not vim.g.vscode,
    config = function()
      local good_colorschemes = {
        'terafox',
        'solarized-osaka',
        'slate',
        'rose-pine-main',
        'retrobox',
        'carbonfox',
        'OceanicNext',
        'nordic',
        'nightfox',
        'kanagawa',
        'gruvbox',
        'github_dark_default',
        'github_dark_dimmed',
        'flexoki-moon-toddler',
        'flexoki-moon-red',
        'flexoki-moon-purple',
        'flexoki-moon-green',
        'flexoki-moon-black',
      }

      local function get_random_colorscheme()
        math.randomseed(os.time())
        local index = math.random(#good_colorschemes)
        return good_colorschemes[index]
      end

      -- === GIT-BASED PERSISTENCE ===
      local data_path = vim.fn.stdpath('data') .. '/git_colorschemes'
      local function ensure_data_dir() vim.fn.mkdir(data_path, 'p') end
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
        if not git_root then return end

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
          callback = function() save_colorscheme() end,
        })

        -- Auto-load when changing directories
        vim.api.nvim_create_autocmd('DirChanged', {
          group = vim.api.nvim_create_augroup('GitColorschemePersiestenceDirChange', { clear = true }),
          callback = function() load_colorscheme() end,
        })
      end

      -- For Telescope to be able to pick from the good colorschemes
      _G.ColorschemeManager = {
        good_colorschemes = good_colorschemes,
        get_random_colorscheme = get_random_colorscheme,
      }

      if not load_colorscheme() then vim.cmd('colorscheme github_dark_dimmed') end

      setup_auto_save()
    end,
  },
}
