package ui

import (
	"context"
	"fmt"
	"io"
	"strings"

	"github.com/atotto/clipboard"
	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/glamour"
	"github.com/charmbracelet/lipgloss"
	"github.com/ichrisbirch/menu/internal/executor"
	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
)

// MenuState tracks what screen we're currently on
type MenuState int

const (
	MainMenu MenuState = iota
	SessionsMenu
	TasksMenu
	NotesMenu
	BookmarksMenu
	ToolsMenu
	CommandsMenu
	WorkflowsMenu
	LearningMenu
	DetailView
	ExecutionResult
)

// Styles for the menu
var (
	titleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("170")).
			Bold(true).
			Padding(0, 1)

	menuItemStyle = lipgloss.NewStyle().
			PaddingLeft(4)

	selectedItemStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("170")).
				Bold(true).
				PaddingLeft(2)

	helpStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("241")).
			Padding(1, 0)

	detailStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("170")).
			Padding(1, 2).
			Margin(1)
)

// menuItem implements list.Item for the main menu
type menuItem struct {
	title string
	key   string // keyboard shortcut
}

func (i menuItem) FilterValue() string { return i.title }

// Simple list delegate for menu items
type menuDelegate struct{}

func (d menuDelegate) Height() int                               { return 1 }
func (d menuDelegate) Spacing() int                              { return 0 }
func (d menuDelegate) Update(msg tea.Msg, m *list.Model) tea.Cmd { return nil }

func (d menuDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	menuItem, ok := item.(menuItem)
	if !ok {
		return
	}

	str := fmt.Sprintf("%s → %s", menuItem.key, menuItem.title)

	if index == m.Index() {
		fmt.Fprint(w, selectedItemStyle.Render("> "+str))
	} else {
		fmt.Fprint(w, menuItemStyle.Render("  "+str))
	}
}

// integrationItem wraps integration.Item for the list
type integrationItem struct {
	item integration.Item
}

func (i integrationItem) FilterValue() string {
	return i.item.Title + " " + i.item.Description
}

// integrationDelegate renders integration items in lists
type integrationDelegate struct{}

func (d integrationDelegate) Height() int                               { return 1 }
func (d integrationDelegate) Spacing() int                              { return 0 }
func (d integrationDelegate) Update(msg tea.Msg, m *list.Model) tea.Cmd { return nil }

func (d integrationDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	integItem, ok := item.(integrationItem)
	if !ok {
		return
	}

	i := integItem.item

	// Format: [★] Icon Title → Description
	// Show favorite indicator
	favoriteIndicator := ""
	if i.Favorite {
		favoriteIndicator = "★ "
	}

	str := fmt.Sprintf("%s%s %s", favoriteIndicator, i.Icon, i.Title)
	if i.Description != "" {
		str = fmt.Sprintf("%s → %s", str, i.Description)
	}

	if index == m.Index() {
		fmt.Fprint(w, selectedItemStyle.Render("> "+str))
	} else {
		fmt.Fprint(w, menuItemStyle.Render("  "+str))
	}
}

// Model is the main menu model
type Model struct {
	state           MenuState
	mainMenu        list.Model
	currentList     list.Model
	loader          *registry.Loader // Deprecated: kept for backward compatibility
	manager         *integration.Manager
	executor        *executor.Executor
	selectedItem    integration.Item // Current integration item
	selectedInteg   integration.Integration // Integration that provided the item
	executionResult *integration.ExecutionResult
	previousState   MenuState // For returning from execution results
	width           int
	height          int
	quitting        bool
	err             error
}

// NewModel creates a new menu model (deprecated - use NewModelWithIntegrations)
func NewModel() Model {
	return newModelInternal(nil)
}

// NewModelWithIntegrations creates a new menu model with integration manager
func NewModelWithIntegrations(manager *integration.Manager) Model {
	return newModelInternal(manager)
}

// newModelInternal is the internal constructor
func newModelInternal(manager *integration.Manager) Model {
	// Create main menu items
	items := []list.Item{
		menuItem{title: "Sessions", key: "s"},
		menuItem{title: "Tasks", key: "t"},
		menuItem{title: "Notes", key: "n"},
		menuItem{title: "Bookmarks", key: "b"},
		menuItem{title: "Tools", key: "o"}, // 'o' for tOols
		menuItem{title: "Commands & Aliases", key: "c"},
		menuItem{title: "Git Workflows", key: "g"},
		menuItem{title: "File Operations", key: "f"},
		menuItem{title: "Vim Workflows", key: "v"},
		menuItem{title: "Vim Keybindings", key: "k"},
		menuItem{title: "Learning Topics", key: "l"},
		menuItem{title: "Quit", key: "q"},
	}

	mainList := list.New(items, menuDelegate{}, 0, 0)
	mainList.Title = "Universal Menu"
	mainList.Styles.Title = titleStyle
	mainList.SetShowStatusBar(false)
	mainList.SetFilteringEnabled(false)

	return Model{
		state:    MainMenu,
		mainMenu: mainList,
		loader:   registry.NewLoader(), // Keep for backward compatibility
		manager:  manager,
		executor: executor.NewExecutor(),
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

// Helper methods to load items from specific integrations

// loadIntegrationItems loads items from a specific integration by name
func (m *Model) loadIntegrationItems(integrationName string) ([]integration.Item, error) {
	if m.manager == nil {
		return nil, fmt.Errorf("integration manager not initialized")
	}

	ctx := context.Background()
	integ, err := m.manager.Get(integrationName)
	if err != nil {
		return nil, err
	}

	items, err := integ.Load(ctx)
	if err != nil {
		return nil, err
	}

	// Enrich items with favorite and recent status
	items = m.manager.EnrichItems(integrationName, items)

	return items, nil
}

// createListFromItems creates a bubbles list from integration items
func (m *Model) createListFromItems(items []integration.Item, title string) list.Model {
	listItems := make([]list.Item, len(items))
	for i, item := range items {
		listItems[i] = integrationItem{
			item: item,
		}
	}

	l := list.New(listItems, integrationDelegate{}, m.width, m.height-4)
	l.Title = title
	l.Styles.Title = titleStyle
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(true)

	return l
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.mainMenu.SetSize(msg.Width, msg.Height-4)
		if m.state != MainMenu {
			m.currentList.SetSize(msg.Width, msg.Height-4)
		}
		return m, nil

	case tea.KeyMsg:
		switch m.state {
		case MainMenu:
			return m.handleMainMenuKeys(msg)
		case SessionsMenu, TasksMenu, NotesMenu, BookmarksMenu, ToolsMenu, CommandsMenu, WorkflowsMenu, LearningMenu:
			return m.handleSubmenuKeys(msg)
		case DetailView:
			return m.handleDetailKeys(msg)
		case ExecutionResult:
			return m.handleExecutionResultKeys(msg)
		}
	}

	// Update the appropriate list
	var cmd tea.Cmd
	if m.state == MainMenu {
		m.mainMenu, cmd = m.mainMenu.Update(msg)
	} else if m.state == SessionsMenu || m.state == TasksMenu || m.state == NotesMenu ||
		m.state == BookmarksMenu || m.state == ToolsMenu || m.state == CommandsMenu ||
		m.state == WorkflowsMenu || m.state == LearningMenu {
		m.currentList, cmd = m.currentList.Update(msg)
	}

	return m, cmd
}

// handleMainMenuKeys handles keyboard input on the main menu
func (m Model) handleMainMenuKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c", "q":
		m.quitting = true
		return m, tea.Quit

	// Direct keyboard shortcuts
	case "s":
		return m.showIntegrationMenu("sessions", "Sessions", SessionsMenu)
	case "t":
		return m.showIntegrationMenu("tasks", "Tasks", TasksMenu)
	case "n":
		return m.showIntegrationMenu("notes", "Notes", NotesMenu)
	case "b":
		return m.showIntegrationMenu("bookmarks", "Bookmarks", BookmarksMenu)
	case "o":
		return m.showIntegrationMenu("tools", "Tools", ToolsMenu)
	case "c":
		return m.showIntegrationMenu("commands", "Commands & Aliases", CommandsMenu)
	case "g", "v", "f", "k":
		return m.showIntegrationMenu("workflows", "Workflows", WorkflowsMenu)
	case "l":
		return m.showIntegrationMenu("learning", "Learning Topics", LearningMenu)

	case "enter":
		// Handle selection from main menu
		selected := m.mainMenu.SelectedItem()
		if item, ok := selected.(menuItem); ok {
			switch item.key {
			case "s":
				return m.showIntegrationMenu("sessions", "Sessions", SessionsMenu)
			case "t":
				return m.showIntegrationMenu("tasks", "Tasks", TasksMenu)
			case "n":
				return m.showIntegrationMenu("notes", "Notes", NotesMenu)
			case "b":
				return m.showIntegrationMenu("bookmarks", "Bookmarks", BookmarksMenu)
			case "o":
				return m.showIntegrationMenu("tools", "Tools", ToolsMenu)
			case "c":
				return m.showIntegrationMenu("commands", "Commands & Aliases", CommandsMenu)
			case "g", "v", "f", "k":
				return m.showIntegrationMenu("workflows", "Workflows", WorkflowsMenu)
			case "l":
				return m.showIntegrationMenu("learning", "Learning Topics", LearningMenu)
			case "q":
				m.quitting = true
				return m, tea.Quit
			}
		}
	}

	// Update the list for other keys (navigation)
	var cmd tea.Cmd
	m.mainMenu, cmd = m.mainMenu.Update(msg)
	return m, cmd
}

// showIntegrationMenu displays items from a specific integration
func (m Model) showIntegrationMenu(integrationName, title string, state MenuState) (tea.Model, tea.Cmd) {
	if m.manager == nil {
		m.err = fmt.Errorf("integration manager not initialized")
		return m, nil
	}

	items, err := m.loadIntegrationItems(integrationName)
	if err != nil {
		m.err = err
		return m, nil
	}

	m.currentList = m.createListFromItems(items, title)
	m.state = state
	return m, nil
}

// handleSubmenuKeys handles keyboard input in submenus
func (m Model) handleSubmenuKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		m.quitting = true
		return m, tea.Quit

	case "esc", "q":
		// Go back to main menu
		m.state = MainMenu
		m.err = nil
		return m, nil

	case "enter":
		// Show detail view or execute
		selected := m.currentList.SelectedItem()
		if item, ok := selected.(integrationItem); ok {
			m.selectedItem = item.item
			m.previousState = m.state
			m.state = DetailView
			return m, nil
		}
	}

	// Update list for navigation
	var cmd tea.Cmd
	m.currentList, cmd = m.currentList.Update(msg)
	return m, cmd
}

// handleDetailKeys handles keyboard input in detail view
func (m Model) handleDetailKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		m.quitting = true
		return m, tea.Quit

	case "esc", "q":
		// Go back to previous menu
		m.state = m.previousState
		m.err = nil
		return m, nil

	case "f":
		// Toggle favorite
		if m.manager != nil {
			err := m.manager.ToggleFavorite(m.selectedItem.Source, m.selectedItem.ID)
			if err != nil {
				m.err = fmt.Errorf("failed to toggle favorite: %v", err)
			} else {
				// Update the item's favorite status
				m.selectedItem.Favorite = !m.selectedItem.Favorite

				// Reload the list to show updated favorite indicator
				if items, err := m.loadIntegrationItems(m.selectedItem.Source); err == nil {
					m.currentList = m.createListFromItems(items, m.currentList.Title)
				}
			}
		}
		return m, nil

	case "c":
		// Copy command to clipboard
		if m.selectedItem.Command != "" {
			err := clipboard.WriteAll(m.selectedItem.Command)
			if err != nil {
				m.err = fmt.Errorf("failed to copy to clipboard: %v", err)
			} else {
				// Show success message by clearing any previous error
				m.err = nil
			}
		}
		return m, nil

	case "e", "enter":
		// Execute the item if executable
		if m.selectedItem.Executable {
			return m.executeItem()
		}
	}

	return m, nil
}

// handleExecutionResultKeys handles keyboard input in execution result view
func (m Model) handleExecutionResultKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		m.quitting = true
		return m, tea.Quit

	case "esc", "q", "enter":
		// Go back to previous menu
		m.state = m.previousState
		m.executionResult = nil
		m.err = nil
		return m, nil
	}

	return m, nil
}

// executeItem executes the selected integration item
func (m Model) executeItem() (tea.Model, tea.Cmd) {
	if m.manager == nil {
		m.err = fmt.Errorf("integration manager not initialized")
		return m, nil
	}

	// Get the integration that provided this item
	ctx := context.Background()
	integ, err := m.manager.Get(m.selectedItem.Source)
	if err != nil {
		m.err = fmt.Errorf("integration not found: %s", m.selectedItem.Source)
		return m, nil
	}

	// Get the command to execute
	command, err := integ.Execute(ctx, m.selectedItem)
	if err != nil {
		m.err = fmt.Errorf("execution failed: %v", err)
		return m, nil
	}

	// Validate the command
	if err := m.executor.ValidateCommand(command); err != nil {
		m.err = fmt.Errorf("unsafe command: %v", err)
		return m, nil
	}

	// Execute the command
	result, err := m.executor.Execute(ctx, command, m.selectedItem.IsInteractive)
	if err != nil {
		m.err = fmt.Errorf("execution error: %v", err)
		return m, nil
	}

	// Mark as recent if execution was successful
	if result.Success {
		_ = m.manager.MarkRecent(m.selectedItem.Source, m.selectedItem.ID)
	}

	// Store result and switch to result view
	m.executionResult = result
	m.state = ExecutionResult

	return m, nil
}

func (m Model) View() string {
	if m.quitting {
		return ""
	}

	// Show error if present
	var errorMsg string
	if m.err != nil {
		errorStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			Bold(true).
			Padding(1, 2)
		errorMsg = errorStyle.Render(fmt.Sprintf("Error: %v", m.err)) + "\n"
	}

	switch m.state {
	case MainMenu:
		help := helpStyle.Render("Navigate: ↑↓  Select: Enter  Shortcuts: s/t/n/b/o/c/g/l  Quit: q")
		return errorMsg + m.mainMenu.View() + "\n" + help

	case SessionsMenu, TasksMenu, NotesMenu, BookmarksMenu, ToolsMenu, CommandsMenu, WorkflowsMenu, LearningMenu:
		help := helpStyle.Render("Navigate: ↑↓  View: Enter  Back: Esc  Quit: Ctrl+C")
		return errorMsg + m.currentList.View() + "\n" + help

	case DetailView:
		execHint := ""
		if m.selectedItem.Executable {
			execHint = "  Execute: Enter or e"
		}
		copyHint := ""
		if m.selectedItem.Command != "" {
			copyHint = "  Copy: c"
		}
		favoriteHint := "  Toggle Favorite: f"
		help := helpStyle.Render(fmt.Sprintf("Back: Esc%s%s%s  Quit: Ctrl+C", execHint, copyHint, favoriteHint))
		return errorMsg + m.renderDetail() + "\n" + help

	case ExecutionResult:
		help := helpStyle.Render("Back: Enter/Esc  Quit: Ctrl+C")
		return errorMsg + m.renderExecutionResult() + "\n" + help

	default:
		return "Unknown state"
	}
}

// renderExecutionResult renders the execution result view
func (m Model) renderExecutionResult() string {
	if m.executionResult == nil {
		return "No execution result"
	}

	var content strings.Builder

	// Header with item title
	content.WriteString(titleStyle.Render(fmt.Sprintf("Execution: %s", m.selectedItem.Title)))
	content.WriteString("\n\n")

	// Result status
	if m.executionResult.Success {
		successStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("46")).
			Bold(true)
		content.WriteString(successStyle.Render("✓ Success"))
	} else {
		errorStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			Bold(true)
		content.WriteString(errorStyle.Render("✗ Failed"))
	}

	content.WriteString(fmt.Sprintf(" (took %dms, exit code: %d)\n\n", m.executionResult.Duration, m.executionResult.ExitCode))

	// Output
	if m.executionResult.Output != "" {
		content.WriteString("Output:\n")
		outputStyle := lipgloss.NewStyle().
			Padding(1, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240"))
		content.WriteString(outputStyle.Render(m.executionResult.Output))
		content.WriteString("\n")
	}

	// Error details if present
	if m.executionResult.Error != nil {
		content.WriteString("\nError Details:\n")
		errorStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			Padding(1, 2)
		content.WriteString(errorStyle.Render(m.executionResult.Error.Error()))
	}

	return detailStyle.Render(content.String())
}

// Render detail view for the selected item
func (m Model) renderDetail() string {
	item := m.selectedItem
	var content strings.Builder

	// Title with icon and favorite indicator
	favoriteIndicator := ""
	if item.Favorite {
		favoriteIndicator = "★ "
	}
	header := fmt.Sprintf("%s%s %s", favoriteIndicator, item.Icon, item.Title)
	content.WriteString(titleStyle.Render(header))
	content.WriteString("\n\n")

	// Basic info
	if item.Category != "" {
		content.WriteString(fmt.Sprintf("Category: %s\n", item.Category))
	}
	if item.Status != "" {
		content.WriteString(fmt.Sprintf("Status: %s\n", item.Status))
	}
	if item.Favorite {
		favStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("226")). // Yellow/gold
			Bold(true)
		content.WriteString(favStyle.Render("★ Favorite\n"))
	}
	if item.Description != "" {
		content.WriteString(fmt.Sprintf("Description: %s\n", item.Description))
	}
	content.WriteString("\n")

	// Command if executable
	if item.Executable && item.Command != "" {
		cmdStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color("46")).
			Bold(true)
		content.WriteString(cmdStyle.Render("Command:\n"))

		// Render command with syntax highlighting
		highlighted := renderCodeBlock(item.Command, "bash")
		content.WriteString(highlighted)
		content.WriteString("\n")
	}

	// Tags and keywords
	if len(item.Tags) > 0 {
		content.WriteString(fmt.Sprintf("Tags: %s\n", strings.Join(item.Tags, ", ")))
	}
	if len(item.Keywords) > 0 {
		content.WriteString(fmt.Sprintf("Keywords: %s\n", strings.Join(item.Keywords, ", ")))
	}
	if len(item.Tags) > 0 || len(item.Keywords) > 0 {
		content.WriteString("\n")
	}

	// Integration-specific details from Details map
	if len(item.Details) > 0 {
		m.renderItemDetails(&content, item.Details)
	}

	return detailStyle.Render(content.String())
}

// renderItemDetails renders integration-specific details from the Details map
func (m Model) renderItemDetails(content *strings.Builder, details map[string]interface{}) {
	// Examples
	if examples, ok := details["examples"].([]interface{}); ok && len(examples) > 0 {
		content.WriteString("Examples:\n")
		for _, ex := range examples {
			if exMap, ok := ex.(map[string]interface{}); ok {
				cmd := exMap["cmd"]
				desc := exMap["desc"]
				if cmdStr, ok := cmd.(string); ok {
					// Render command with syntax highlighting
					highlighted := renderCodeBlock(cmdStr, "bash")
					content.WriteString(highlighted)
					content.WriteString(fmt.Sprintf("\n  %v\n\n", desc))
				} else {
					content.WriteString(fmt.Sprintf("  %v - %v\n", cmd, desc))
				}
			}
		}
		content.WriteString("\n")
	}

	// Steps (for workflows)
	if steps, ok := details["steps"].([]interface{}); ok && len(steps) > 0 {
		content.WriteString("Steps:\n")
		for i, step := range steps {
			if stepMap, ok := step.(map[string]interface{}); ok {
				key := stepMap["key"]
				desc := stepMap["description"]
				if key != nil && key != "" {
					content.WriteString(fmt.Sprintf("%d. %v: %v\n", i+1, key, desc))
				} else {
					content.WriteString(fmt.Sprintf("%d. %v\n", i+1, desc))
				}
			}
		}
		content.WriteString("\n")
	}

	// Resources (for learning topics)
	if resources, ok := details["resources"].([]interface{}); ok && len(resources) > 0 {
		content.WriteString("Resources:\n")
		for _, res := range resources {
			if resMap, ok := res.(map[string]interface{}); ok {
				resType := resMap["type"]
				switch resType {
				case "bookmark":
					content.WriteString(fmt.Sprintf("  🔖 %v - %v\n", resMap["title"], resMap["url"]))
				case "note":
					content.WriteString(fmt.Sprintf("  📝 %v (%v)\n", resMap["description"], resMap["path"]))
				case "video":
					content.WriteString(fmt.Sprintf("  🎥 %v - %v\n", resMap["title"], resMap["url"]))
				}
			}
		}
		content.WriteString("\n")
	}

	// Progress (for learning topics)
	if progress, ok := details["progress"].(map[string]interface{}); ok {
		content.WriteString("Progress:\n")
		if started, ok := progress["started"].(string); ok && started != "" {
			content.WriteString(fmt.Sprintf("  Started: %s\n", started))
		}
		if confidence, ok := progress["confidence"].(string); ok && confidence != "" {
			content.WriteString(fmt.Sprintf("  Confidence: %s\n", confidence))
		}
		content.WriteString("\n")
	}

	// Practice exercises
	if exercises, ok := details["exercises"].([]string); ok && len(exercises) > 0 {
		content.WriteString("Practice Exercises:\n")
		for _, ex := range exercises {
			content.WriteString(fmt.Sprintf("  • %s\n", ex))
		}
		content.WriteString("\n")
	}

	// Notes
	if notes, ok := details["notes"].(string); ok && notes != "" {
		content.WriteString(fmt.Sprintf("Notes:\n%s\n\n", notes))
	}

	// URL (for bookmarks/tools)
	if url, ok := details["url"].(string); ok && url != "" {
		content.WriteString(fmt.Sprintf("URL: %s\n\n", url))
	}

	// Documentation URL
	if docsURL, ok := details["docs_url"].(string); ok && docsURL != "" {
		content.WriteString(fmt.Sprintf("Documentation: %s\n\n", docsURL))
	}
}

// renderCodeBlock renders a code block with syntax highlighting
func renderCodeBlock(code, language string) string {
	// Create markdown code block
	markdown := fmt.Sprintf("```%s\n%s\n```", language, code)

	// Create glamour renderer with dark style
	r, err := glamour.NewTermRenderer(
		glamour.WithStylePath("dark"),
		glamour.WithWordWrap(120),
	)
	if err != nil {
		// Fallback to plain code block if glamour fails
		codeStyle := lipgloss.NewStyle().
			Padding(1, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240"))
		return codeStyle.Render(code)
	}

	// Render with syntax highlighting
	out, err := r.Render(markdown)
	if err != nil {
		// Fallback to plain code block
		codeStyle := lipgloss.NewStyle().
			Padding(1, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240"))
		return codeStyle.Render(code)
	}

	return strings.TrimSpace(out)
}
