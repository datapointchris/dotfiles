return {
  {
    'olimorris/codecompanion.nvim',
    -- Only load when NVIM_AI_ENABLED is true
    cond = vim.env.NVIM_AI_ENABLED == 'true',
    dependencies = {
      'nvim-lua/plenary.nvim',
      'nvim-treesitter/nvim-treesitter',
      'nvim-telescope/telescope.nvim',
      'echasnovski/mini.diff',
    },
    opts = {
      -- Direct adapter configuration following documentation
      strategies = {
        chat = {
          adapter = 'anthropic', -- Direct Claude connection for fastest response
          variables = {
            ['buffer'] = {
              opts = {
                default_params = 'watch', -- Auto-watch buffers for real-time updates
              },
            },
          },
          tools = {
            opts = {
              auto_submit_errors = true, -- Auto-send errors to LLM for debugging
              auto_submit_success = false, -- Manual control over success messages
              default_tools = {
                'cmd_runner',
                'insert_edit_into_file',
                'ripgrep_search', -- Use ripgrep instead of grep for speed
                'repository_analyzer', -- Custom repository analysis tool
              },
            },
            ['cmd_runner'] = {
              opts = {
                requires_approval = true, -- Keep safety for command execution
              },
            },
            ['ripgrep_search'] = {
              callback = function(args)
                -- Simple ripgrep search
                local pattern = args and args.pattern or ''
                if pattern == '' then return "Please provide a search pattern: @ripgrep_search pattern='your_search'" end

                local results = vim.fn.systemlist("rg --line-number --context=2 '" .. pattern .. "'")
                if #results == 0 then return 'No results found for: ' .. pattern end

                -- Limit results to prevent overflow
                local limited_results = {}
                for i = 1, math.min(#results, 20) do
                  table.insert(limited_results, results[i])
                end

                return "Search results for '" .. pattern .. "':\n" .. table.concat(limited_results, '\n')
              end,
              description = 'Search code with ripgrep',
              opts = {
                requires_approval = false,
              },
            },
            ['repository_analyzer'] = {
              callback = function(args)
                -- Simple repository analysis
                local analysis_type = args and args.type or 'overview'

                if analysis_type == 'overview' then
                  local total_files = vim.fn.system('fd -t f . | wc -l'):gsub('%s+', '')
                  local git_branch = vim.fn.system('git branch --show-current 2>/dev/null'):gsub('%s+', '')
                  local file_types = vim.fn.systemlist("fd -t f . | rg -o '\\.[^.]+$' | sort | uniq -c | sort -rn | head -5")

                  local result = 'Repository Overview:\n'
                  result = result .. '==================\n'
                  if git_branch ~= '' then result = result .. 'Git branch: ' .. git_branch .. '\n' end
                  result = result .. 'Total files: ' .. total_files .. '\n'
                  result = result .. 'File types:\n' .. table.concat(file_types, '\n')

                  return result
                elseif analysis_type == 'config' then
                  local config_files = vim.fn.systemlist('fd -e lua -e json -e yaml -e yml -e toml . | head -15')
                  return 'Configuration files:\n' .. table.concat(config_files, '\n')
                elseif analysis_type == 'dependencies' then
                  local deps = {}
                  local package_json = vim.fn.systemlist('fd package.json .')
                  local requirements = vim.fn.systemlist('fd requirements.txt .')
                  local cargo_toml = vim.fn.systemlist('fd Cargo.toml .')

                  if #package_json > 0 then table.insert(deps, 'Found Node.js project: ' .. package_json[1]) end
                  if #requirements > 0 then table.insert(deps, 'Found Python project: ' .. requirements[1]) end
                  if #cargo_toml > 0 then table.insert(deps, 'Found Rust project: ' .. cargo_toml[1]) end

                  local lua_requires = vim.fn.systemlist('rg "require\\(" --type lua | head -5')
                  if #lua_requires > 0 then
                    table.insert(deps, '\nLua requires:')
                    for _, req in ipairs(lua_requires) do
                      table.insert(deps, req)
                    end
                  end

                  return #deps > 0 and table.concat(deps, '\n') or 'No dependencies found'
                end

                return 'Analysis type not supported'
              end,
              description = 'Analyze repository (overview, config, dependencies)',
              opts = {
                requires_approval = false,
              },
            },
          },
          keymaps = {
            send = {
              modes = { n = '<C-s>', i = '<C-s>' },
              opts = { desc = 'Send message to LLM' },
            },
            close = {
              modes = { n = '<C-c>', i = '<C-c>' },
              opts = { desc = 'Close chat buffer' },
            },
            stop = {
              modes = { n = 'q' },
              opts = { desc = 'Stop current request' },
            },
          },
          roles = {
            llm = function(adapter) return 'Claude (' .. adapter.formatted_name .. ')' end,
            user = 'Me',
          },
        },
        inline = {
          adapter = 'anthropic', -- Consistent adapter across strategies
          keymaps = {
            accept_change = {
              modes = { n = 'gda' },
              opts = { desc = 'Accept diff change' },
            },
            reject_change = {
              modes = { n = 'gdr' },
              opts = { desc = 'Reject diff change' },
            },
            always_accept = {
              modes = { n = 'gdy' },
              opts = { desc = 'Accept all changes' },
            },
          },
        },
      },

      -- Configure adapters for optimal Claude experience
      adapters = {
        http = {
          anthropic = function()
            return require('codecompanion.adapters').extend('anthropic', {
              schema = {
                model = {
                  default = 'claude-3-5-sonnet-20241022',
                },
              },
            })
          end,
        },
      },

      -- Custom slash commands for quick access
      slash_commands = {
        web = {
          callback = function(args)
            local query = args and table.concat(args, ' ') or ''
            if query == '' then return 'Usage: /web your search query here' end

            local search_url = 'https://duckduckgo.com/?q=' .. vim.fn.shellescape(query)
            local result = '🔍 Web Search: ' .. query .. '\n\n'
            result = result .. 'Search URL: ' .. search_url .. '\n\n'
            result = result .. 'For instant answers, use @web_search tool.'

            return result
          end,
          description = 'Quick web search reference',
        },

        repo = {
          callback = function()
            local files = vim.fn.systemlist('fd -t f . | head -15')
            local git_branch = vim.fn.system('git branch --show-current 2>/dev/null'):gsub('%s+', '')

            local result = '📁 Repository Overview\n'
            if git_branch ~= '' then result = result .. 'Branch: ' .. git_branch .. '\n' end
            result = result .. '\nKey files:\n' .. table.concat(files, '\n')

            return result
          end,
          description = 'Repository overview',
        },
      },

      -- Custom tools for enhanced functionality
      tools = {
        web_search = {
          callback = function(args)
            local query = args and args.query or ''
            if query == '' then return "Usage: @web_search query='your search terms'" end

            local escaped_query = query:gsub(' ', '+')
            local cmd = string.format("curl -s 'https://api.duckduckgo.com/?q=%s&format=json&no_redirect=1&skip_disambig=1'", escaped_query)
            local handle = io.popen(cmd)

            if handle then
              local response = handle:read('*a')
              handle:close()

              local success, json = pcall(vim.fn.json_decode, response)
              if success and json and json.AbstractText and json.AbstractText ~= '' then
                local result = '🌐 Web Search: ' .. query .. '\n\n'
                result = result .. json.AbstractText
                if json.AbstractURL then result = result .. '\n\nSource: ' .. json.AbstractURL end
                return result
              else
                return '🌐 Web Search: '
                  .. query
                  .. '\n\nNo instant answer found. Search manually at: https://duckduckgo.com/?q='
                  .. escaped_query
              end
            end

            return 'Web search unavailable - check internet connection'
          end,
          description = 'Search the web for information',
          opts = {
            requires_approval = false,
          },
        },

        quick_search = {
          callback = function(args)
            local pattern = args and args.pattern or ''
            if pattern == '' then return "Usage: @quick_search pattern='search term'" end

            local results = vim.fn.systemlist("rg --line-number --context=1 --max-count=10 '" .. pattern .. "'")
            if #results == 0 then return 'No results found for: ' .. pattern end

            return '🔍 Quick Search: ' .. pattern .. '\n\n' .. table.concat(results, '\n')
          end,
          description = 'Quick code search with ripgrep',
          opts = {
            requires_approval = false,
          },
        },
      },

      -- Memory configuration (following documentation)
      memory = {
        opts = {
          chat = {
            enabled = true,
            default_memory = { 'claude', 'project' },
          },
        },

        claude = {
          description = 'Personal AI context and preferences',
          parser = 'claude',
          files = {
            'CLAUDE.md',
            '~/.claude/CLAUDE.md',
          },
        },

        project = {
          description = 'Project context and guidelines',
          parser = 'claude',
          files = {
            'README.md',
            '.cursorrules',
            'CONTRIBUTING.md',
          },
        },
      },

      -- Optimized display for quick interactions
      display = {
        action_palette = {
          provider = 'telescope',
        },

        chat = {
          show_settings = false,
          intro_message = '💬 Quick AI assistant ready! Use /web for web search, #{buffer} for current file context.',

          window = {
            layout = 'vertical',
            position = 'right',
            width = 0.35,
            height = 0.8,
            border = 'rounded',
            opts = {
              wrap = true,
              number = false,
              relativenumber = false,
            },
          },
        },

        diff = {
          enabled = true,
          provider = 'mini_diff',
        },
      },

      -- General options for optimal performance
      log_level = 'ERROR',
      send_code = true,
      use_default_actions = true,
    },

    config = function(_, opts) require('codecompanion').setup(opts) end,
  },

  {
    'echasnovski/mini.diff',
    config = function()
      local diff = require('mini.diff')
      diff.setup({
        source = diff.gen_source.none(), -- Disabled by default, CodeCompanion will enable when needed
      })
    end,
  },
}
