# Bubbletea Quick Reference Card

## Core Pattern

```go
type model struct {
    // Your state here
    list list.Model
    commands []Command
    selected Command
}

func (m model) Init() tea.Cmd {
    // Return initial command (or nil)
    return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "q", "ctrl+c":
            return m, tea.Quit
        case "enter":
            // Do something
            return m, someCommand
        }
    }

    // Delegate to child components
    var cmd tea.Cmd
    m.list, cmd = m.list.Update(msg)
    return m, cmd
}

func (m model) View() string {
    return m.list.View()
}
```

## Essential Imports

```go
import (
    "github.com/charmbracelet/bubbletea"
    "github.com/charmbracelet/bubbles/list"
    "github.com/charmbracelet/lipgloss"
    "github.com/spf13/cobra"
    "github.com/spf13/viper"
)
```

## List Component

```go
// Define item
type item struct {
    title, desc string
}

func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title }

// Create list
items := []list.Item{
    item{title: "Commands", desc: "Shell commands"},
}

l := list.New(items, list.NewDefaultDelegate(), 80, 20)
l.Title = "Menu"
l.SetShowStatusBar(false)
l.SetFilteringEnabled(true)

// Get selection
selected := m.list.SelectedItem().(item)
```

## Styling with Lipgloss

```go
var (
    titleStyle = lipgloss.NewStyle().
        Bold(true).
        Foreground(lipgloss.Color("170")).
        Padding(1, 2).
        Border(lipgloss.RoundedBorder()).
        BorderForeground(lipgloss.Color("63"))

    selectedStyle = lipgloss.NewStyle().
        Foreground(lipgloss.Color("170")).
        Bold(true)

    dimStyle = lipgloss.NewStyle().
        Foreground(lipgloss.Color("241"))
)

// Adaptive colors (light/dark)
adaptiveColor := lipgloss.AdaptiveColor{
    Light: "16",  // Dark text for light bg
    Dark: "255",  // Light text for dark bg
}
```

## External Commands

```go
// Non-interactive (task, git status, etc.)
func runTask(name string) tea.Cmd {
    return func() tea.Msg {
        cmd := exec.Command("task", name)
        output, err := cmd.CombinedOutput()
        return taskFinishedMsg{output, err}
    }
}

// Interactive (vim, tmux, etc.)
func openEditor(file string) tea.Cmd {
    c := exec.Command(os.Getenv("EDITOR"), file)
    return tea.ExecProcess(c, func(err error) tea.Msg {
        return editorFinishedMsg{err}
    })
}
```

## Configuration with Viper

```go
type Config struct {
    Menu struct {
        Height int `mapstructure:"height"`
        PreviewEnabled bool `mapstructure:"preview_enabled"`
    } `mapstructure:"menu"`

    Registry struct {
        Commands string `mapstructure:"commands"`
    } `mapstructure:"registry"`
}

func LoadConfig() (*Config, error) {
    viper.SetConfigName("config")
    viper.SetConfigType("yaml")
    viper.AddConfigPath("$HOME/.config/menu")

    if err := viper.ReadInConfig(); err != nil {
        return nil, err
    }

    var cfg Config
    if err := viper.Unmarshal(&cfg); err != nil {
        return nil, err
    }

    return &cfg, nil
}
```

## YAML Parsing

```go
import "gopkg.in/yaml.v3"

type Command struct {
    Name        string   `yaml:"name"`
    Type        string   `yaml:"type"`
    Description string   `yaml:"description"`
    Keywords    []string `yaml:"keywords"`
    Command     string   `yaml:"command"`
    Examples    []struct {
        Command     string `yaml:"command"`
        Description string `yaml:"description"`
    } `yaml:"examples"`
    Notes    string   `yaml:"notes"`
    Related  []string `yaml:"related"`
    Platform string   `yaml:"platform"`
}

func loadCommands(path string) ([]Command, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }

    var commands []Command
    if err := yaml.Unmarshal(data, &commands); err != nil {
        return nil, err
    }

    return commands, nil
}
```

## Cobra Integration

```go
var rootCmd = &cobra.Command{
    Use:   "menu",
    Short: "Universal menu system",
    RunE: func(cmd *cobra.Command, args []string) error {
        p := tea.NewProgram(initialModel())
        if _, err := p.Run(); err != nil {
            return err
        }
        return nil
    },
}

var sessCmd = &cobra.Command{
    Use:   "sess",
    Short: "Session management",
    RunE: func(cmd *cobra.Command, args []string) error {
        p := tea.NewProgram(newSessionModel())
        return p.Start()
    },
}

func init() {
    rootCmd.AddCommand(sessCmd)
}

func main() {
    if err := rootCmd.Execute(); err != nil {
        os.Exit(1)
    }
}
```

## State Management

```go
// Multi-view navigation
type view int

const (
    viewMenu view = iota
    viewCommands
    viewSessions
    viewDetails
)

type model struct {
    currentView view
    menuModel   menuModel
    commandsModel commandsModel
    // ...
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch m.currentView {
    case viewMenu:
        return m.updateMenu(msg)
    case viewCommands:
        return m.updateCommands(msg)
    // ...
    }
}

func (m model) View() string {
    switch m.currentView {
    case viewMenu:
        return m.menuModel.View()
    case viewCommands:
        return m.commandsModel.View()
    // ...
    }
}
```

## Common Key Bindings

```go
case tea.KeyMsg:
    switch msg.String() {
    case "q", "ctrl+c":
        return m, tea.Quit
    case "esc":
        m.currentView = viewMenu
        return m, nil
    case "enter":
        item := m.list.SelectedItem().(myItem)
        return m, handleSelection(item)
    case "j", "down":
        m.list.CursorDown()
    case "k", "up":
        m.list.CursorUp()
    case "/":
        m.list.SetFilteringEnabled(true)
    }
```

## Window Size Handling

```go
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.WindowSizeMsg:
        m.list.SetWidth(msg.Width)
        m.list.SetHeight(msg.Height - 4)  // Leave space for header
        return m, nil
    }
    // ...
}
```

## Testing

```go
import "github.com/charmbracelet/x/exp/teatest"

func TestModel(t *testing.T) {
    m := initialModel()
    tm := teatest.NewTestModel(t, m)

    // Send keys
    tm.Send(tea.KeyMsg{Type: tea.KeyDown})
    tm.Send(tea.KeyMsg{Type: tea.KeyEnter})

    // Wait for specific output
    teatest.WaitFor(
        t, tm.Output(),
        func(bts []byte) bool {
            return strings.Contains(string(bts), "Success")
        },
        teatest.WithDuration(time.Second),
    )
}
```

## Common Patterns

### Async Loading

```go
type dataLoadedMsg struct {
    data []Command
    err  error
}

func loadDataCmd() tea.Msg {
    data, err := loadCommands("commands.yml")
    return dataLoadedMsg{data, err}
}

func (m model) Init() tea.Cmd {
    return loadDataCmd
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case dataLoadedMsg:
        if msg.err != nil {
            m.err = msg.err
            return m, nil
        }
        m.commands = msg.data
        m.list.SetItems(toListItems(msg.data))
        return m, nil
    }
}
```

### Progress Indicator

```go
import "github.com/charmbracelet/bubbles/spinner"

type model struct {
    spinner  spinner.Model
    loading  bool
}

func (m model) Init() tea.Cmd {
    return tea.Batch(
        m.spinner.Tick,
        loadDataCmd,
    )
}

func (m model) View() string {
    if m.loading {
        return m.spinner.View() + " Loading..."
    }
    return m.list.View()
}
```

## Debugging

```go
import "github.com/davecgh/go-spew/spew"

// Log messages to file
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    if os.Getenv("DEBUG") == "true" {
        f, _ := os.OpenFile("/tmp/bubbletea.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
        spew.Fdump(f, msg)
        f.Close()
    }
    // ...
}
```

## Resources

- Docs: github.com/charmbracelet/bubbletea
- Examples: github.com/charmbracelet/bubbletea/tree/main/examples
- Gum source: github.com/charmbracelet/gum
- Best practices: leg100.github.io/en/posts/building-bubbletea-programs
- Detailed research: [Go TUI Ecosystem Research](../../learnings/go-tui-ecosystem-research.md)
