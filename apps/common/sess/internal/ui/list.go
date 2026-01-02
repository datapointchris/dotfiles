package ui

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/datapointchris/sess/internal/session"
)

// Styles for the UI
// lipgloss is like CSS for the terminal
var (
	// docStyle applies to the whole list
	docStyle = lipgloss.NewStyle().Margin(1, 2)

	// titleStyle is for the list title
	titleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("170")).
			Bold(true)

	// itemStyle is for regular list items
	itemStyle = lipgloss.NewStyle().PaddingLeft(2)

	// selectedItemStyle is for the currently selected item
	selectedItemStyle = lipgloss.NewStyle().
				PaddingLeft(1).
				Foreground(lipgloss.Color("170")).
				Bold(true)

	// activeStyle is for active sessions (green circle)
	activeStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("10"))

	// tmuxinatorStyle is for tmuxinator projects (yellow gear)
	tmuxinatorStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("11"))

	// defaultStyle is for default sessions (blue circle)
	defaultStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("12"))
)

// sessionItem implements list.Item interface for our sessions
// This is how we adapt our Session type to work with bubbles/list
type sessionItem struct {
	session.Session
}

// FilterValue is required by list.Item
// It returns the value used when filtering the list
func (i sessionItem) FilterValue() string {
	return i.Name
}

// sessionItemDelegate defines how to render list items
// This implements list.ItemDelegate interface
type sessionItemDelegate struct{}

// Height returns how many terminal rows this item takes up
func (d sessionItemDelegate) Height() int { return 1 }

// Spacing returns how many blank lines to add after each item
func (d sessionItemDelegate) Spacing() int { return 0 }

// Update handles messages for individual items
// For our simple case, we don't need custom item updates
func (d sessionItemDelegate) Update(msg tea.Msg, m *list.Model) tea.Cmd {
	return nil
}

// Render draws a single list item
// This is where we apply our custom styling with icons
func (d sessionItemDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	// Type assert the item back to sessionItem
	// The .(sessionItem) is called a "type assertion"
	// The ok variable tells us if the assertion succeeded
	sess, ok := item.(sessionItem)
	if !ok {
		return
	}

	// Build the display string with icon
	icon := sess.Icon()
	display := sess.DisplayInfo()

	// Apply color based on session type
	var styledIcon string
	switch sess.Type {
	case session.SessionTypeTmux:
		styledIcon = activeStyle.Render(icon)
	case session.SessionTypeTmuxinator:
		styledIcon = tmuxinatorStyle.Render(icon)
	case session.SessionTypeDefault:
		styledIcon = defaultStyle.Render(icon)
	}

	// Determine if this item is selected
	// m.Index() returns the currently selected index
	str := fmt.Sprintf("%s %s", styledIcon, display)
	if index == m.Index() {
		// This is the selected item, use selected style
		str = selectedItemStyle.Render("> " + str)
	} else {
		// Regular item
		str = itemStyle.Render("  " + str)
	}

	// Write to the output
	// fmt.Fprint() is like fmt.Print() but writes to a specific writer
	fmt.Fprint(w, str)
}

// Model holds the state of our UI
// This is the "M" in the Elm Architecture (Model-Update-View)
type Model struct {
	list     list.Model      // The list component from bubbles
	sessions []session.Session // All available sessions
	choice   string          // The selected session name (when user presses Enter)
}

// NewModel creates a new UI model
func NewModel(sessions []session.Session) Model {
	// Convert sessions to list items
	items := make([]list.Item, len(sessions))
	for i, sess := range sessions {
		items[i] = sessionItem{sess}
	}

	// Create the list with custom delegate
	delegate := sessionItemDelegate{}
	listModel := list.New(items, delegate, 0, 0)
	listModel.Title = "Tmux Sessions"
	listModel.Styles.Title = titleStyle

	// Additional list settings
	listModel.SetShowStatusBar(false) // We don't need the status bar
	listModel.SetFilteringEnabled(true) // Enable fuzzy search with /

	return Model{
		list:     listModel,
		sessions: sessions,
	}
}

// Init is called when the program starts
// It can return a command to run (or nil)
// This is part of the Elm Architecture
func (m Model) Init() tea.Cmd {
	return nil
}

// Update is called when a message arrives (user input, etc.)
// This is where we handle all events and update the model
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	// msg is a type assertion - we're checking what type of message this is

	case tea.WindowSizeMsg:
		// Window was resized, update list dimensions
		h, v := docStyle.GetFrameSize()
		m.list.SetSize(msg.Width-h, msg.Height-v)
		return m, nil

	case tea.KeyMsg:
		// A key was pressed
		switch msg.String() {
		case "ctrl+c", "q":
			// Quit the program
			return m, tea.Quit

		case "enter":
			// User selected a session
			// Get the selected item
			selected := m.list.SelectedItem()
			if selected != nil {
				sess := selected.(sessionItem)
				m.choice = sess.Name
				// Quit and let main.go handle the session switch
				return m, tea.Quit
			}
		}
	}

	// For all other messages, let the list component handle them
	// This includes arrow keys, filtering, etc.
	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

// View renders the current state of the model
// This returns a string that will be drawn to the terminal
func (m Model) View() string {
	// If user made a choice, don't show the list
	if m.choice != "" {
		return ""
	}

	// Render the list with document style
	return docStyle.Render(m.list.View())
}

// GetChoice returns the user's selection
// This is called after the program exits
func (m Model) GetChoice() string {
	return m.choice
}
