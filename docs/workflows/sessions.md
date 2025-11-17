# Session Management Workflows

Session management transforms how development work happens across multiple projects. Each project gets its own isolated workspace with separate terminals, editors, and tools. The session manager reduces the friction of switching contexts to almost nothing, making it effortless to jump between projects or start fresh workspaces.

## Morning Setup Workflow

Start the day by launching development sessions for active projects. The interactive picker shows everything available in one view - active tmux sessions, configured tmuxinator projects, and default sessions waiting to be started.

```bash
sess
```

The picker displays three types of sessions with visual indicators. Active tmux sessions show `●` meaning they're currently running. Tmuxinator projects show `⚙` indicating configured layouts are available. Default sessions show `○` meaning they haven't been started yet. Navigate with arrow keys, press Enter to select.

For direct access without the picker, jump straight to a session by name. This works whether the session exists or needs to be created. Type the project name and start working immediately.

```bash
sess dotfiles           # Jump to dotfiles session
sess ichrisbirch-dev    # Jump to main project
```

Starting multiple sessions in quick succession builds your development environment rapidly. Launch the main project session, create a separate session for notes, spin up another for testing. Each workspace stays isolated and ready to return to.

## Project Workflow Patterns

Switch between projects without interrupting flow. The session manager handles creation, switching, and attaching automatically based on context. From within tmux, it uses switch-client to move between sessions instantly. From outside tmux, it uses attach-session to connect to existing sessions or create new ones.

```bash
sess other-project      # Switch to another project
sess last               # Jump back to previous session
```

The last command enables rapid alternation between two projects. Working on a feature that requires checking the main codebase for reference? Switch to the other project, check what's needed, switch back. No typing session names or remembering tmux commands.

## Managing Multiple Projects

See what's running before choosing where to work. The list command shows all sessions with their current status.

```bash
sess list
```

Active sessions appear with `●`. Default sessions appear with `○`. Tmuxinator projects appear with `⚙`. This overview reveals what's already running versus what could be started. Five sessions running might mean it's time to close some. No active sessions means a fresh start.

Check what's available when context-switching feels heavy. The list provides a snapshot of the current development environment state without entering any session.

## Creating Quick Sessions

Start a session for one-off tasks that don't need configured environments. When exploring a new codebase or doing temporary work, create a simple session in the current directory.

```bash
cd ~/code/new-project
sess temp-work          # Creates session in current directory
```

Since temp-work isn't a default session, sess creates it wherever you currently are. Perfect for exploratory work, testing ideas, or handling tasks that don't warrant permanent session configurations.

## Default Sessions

Default sessions define the projects worked on regularly. They specify where each session should be created and what layout it should use. Edit the platform-specific YAML file to add or modify default sessions.

On macOS, edit `~/.config/sess/sessions-macos.yml`. On WSL, edit `~/.config/sess/sessions-wsl.yml`. Each platform maintains its own default sessions, allowing different projects on different machines while using the same sess binary.

```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    description: Dotfiles development
    tmuxinator_project: null

  - name: ichrisbirch-dev
    directory: ~/code/ichrisbirch
    description: Main project development
    tmuxinator_project: ichrisbirch-development
```

Each entry requires a name, directory, and description. The tmuxinator_project field is optional. When null, sess creates a simple single-window session in the specified directory. When set to a tmuxinator project name, sess starts that complex layout instead.

### Simple vs Complex Sessions

Simple sessions work great for straightforward projects. The session starts in the right directory with a single window and one pane. Open the editor, run commands, work normally. No complex layouts or pane configurations needed.

```yaml
- name: notes
  directory: ~/notes
  description: Note taking and journaling
  tmuxinator_project: null
```

Complex sessions use tmuxinator projects for precise control over window layout, pane configuration, and startup commands. Define exactly how the environment should look and what commands should run on session creation.

```yaml
- name: ichrisbirch-dev
  directory: ~/code/ichrisbirch
  description: Main project development
  tmuxinator_project: ichrisbirch-development
```

The corresponding tmuxinator project at `~/.config/tmuxinator/ichrisbirch-development.yml` defines the complete environment:

```yaml
name: ichrisbirch-development
root: ~/code/ichrisbirch

windows:
  - editor:
      layout: main-vertical
      panes:
        - nvim
        - # empty pane for terminal
  - server:
      - uv run invoke start-api
  - tests:
      - uv run pytest --watch
```

When sess creates this session, it opens three windows. The editor window splits vertically with nvim running in the main pane. The server window runs the API. The tests window runs pytest in watch mode. The environment is ready to work immediately.

## Integration with Tmux Keybindings

Bind sess to a tmux key for instant access from anywhere. Many setups override the default tmux session picker (prefix + s) with sess's enhanced version. Add this to `tmux.conf`:

```bash
bind-key s run-shell "tmux neww sess"
```

Press prefix + s to launch the interactive session picker. Select a session and switch immediately. This removes the need to exit tmux, run sess, and reattach. The integration feels seamless.

## Composition with Other Tools

Sess outputs clean data designed for piping and composition. Build custom selection interfaces, extract specific fields for scripting, or filter sessions by type.

```bash
# Custom selection with fzf
sess list | fzf

# Extract session names
sess list | awk '{print $2}'

# Count active sessions
sess list | grep -c "●"

# Filter to tmuxinator projects only
sess list | grep "⚙"
```

This composability enables custom workflows beyond the built-in interactive mode. Pipe to fzf for a different selection UI. Extract names for scripts that automate session management. Count sessions to understand environment size.

## Troubleshooting Workflows

When a session doesn't create as expected, the issue usually involves configuration or dependencies. Check that the directory specified in the default session configuration exists. Verify tmuxinator projects exist if configured. Ensure tmux is running when trying to switch sessions from within tmux.

```bash
# Verify config file exists
ls -la ~/.config/sess/sessions-macos.yml

# Check tmuxinator projects
ls ~/.config/tmuxinator/

# Verify tmux is running
tmux info
```

If sess isn't found in PATH, rebuild and reinstall it from source. The binary lives in `~/go/bin/sess` which should be in PATH for Go tools.

```bash
cd ~/dotfiles/apps/common/sess
task install
which sess
```

## Advanced Patterns

### Project-Specific Shell Environments

Combine default sessions with shell environment variables to create project-specific contexts. Start a session that automatically activates virtual environments, sets environment variables, or changes directory contexts.

Tmuxinator projects can include shell commands that run on pane creation. Use these to activate Python virtual environments, load nvm for specific Node versions, or set project-specific environment variables.

```yaml
windows:
  - editor:
      panes:
        - source .venv/bin/activate && nvim
```

### Multiple Sessions Per Project

Create multiple default sessions for the same project with different purposes. One session for development with editor and server. Another session for testing with continuous test runners. A third session for database work.

```yaml
- name: myproject-dev
  directory: ~/code/myproject
  description: Development environment
  tmuxinator_project: myproject-development

- name: myproject-test
  directory: ~/code/myproject
  description: Testing environment
  tmuxinator_project: myproject-testing
```

This separation allows focused workflows. Development session runs the server and editor. Testing session runs test watchers and debugging tools. Switch between them based on current task.

### Session Templates

Use tmuxinator projects as templates for different types of work. Create a web-development template with panes for editor, server, and logs. Create a data-analysis template with panes for Jupyter, database client, and code editor. Reference these templates from default sessions.

The template defines the structure. The default session defines where to apply it. Multiple projects can use the same template structure with different directories.

## See Also

- [Tmux Configuration](/configuration/tmux.md) - Tmux setup and keybindings
- [Tmuxinator Projects](/configuration/tmuxinator.md) - Complex session layouts
- [Menu System](../reference/workflow-tools/menu.md) - Access sessions through menu
