package integration

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// BaseRenderer provides default rendering for items
type BaseRenderer struct{}

// NewRenderer creates a new base renderer
func NewRenderer() *BaseRenderer {
	return &BaseRenderer{}
}

// Styles for rendering
var (
	titleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("170")).
			Bold(true).
			Padding(0, 1)

	headerStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("99")).
			Bold(true)

	labelStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("241"))

	codeStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("114")).
			Background(lipgloss.Color("235")).
			Padding(0, 1)

	keyStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("214")).
			Bold(true)

	detailBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("170")).
			Padding(1, 2).
			Margin(1)
)

// RenderDetail renders the full detail view for an item
func (r *BaseRenderer) RenderDetail(item Item) string {
	var b strings.Builder

	// Title with icon
	title := item.Title
	if item.Icon != "" {
		title = fmt.Sprintf("%s %s", item.Icon, title)
	}
	b.WriteString(titleStyle.Render(title))
	b.WriteString("\n\n")

	// Category and Status
	if item.Category != "" {
		b.WriteString(labelStyle.Render("Category: "))
		b.WriteString(item.Category)
		b.WriteString("\n")
	}

	if item.Status != "" {
		b.WriteString(labelStyle.Render("Status: "))
		b.WriteString(item.Status)
		b.WriteString("\n")
	}

	// Description
	if item.Description != "" {
		b.WriteString("\n")
		b.WriteString(labelStyle.Render("Description:"))
		b.WriteString("\n")
		b.WriteString(item.Description)
		b.WriteString("\n")
	}

	// Tags
	if len(item.Tags) > 0 {
		b.WriteString("\n")
		b.WriteString(labelStyle.Render("Tags: "))
		b.WriteString(strings.Join(item.Tags, ", "))
		b.WriteString("\n")
	}

	// Command (if executable)
	if item.Executable && item.Command != "" {
		b.WriteString("\n")
		b.WriteString(labelStyle.Render("Command:"))
		b.WriteString("\n")
		b.WriteString(codeStyle.Render(item.Command))
		b.WriteString("\n")
	}

	// Render details based on type
	b.WriteString(r.renderDetails(item))

	// Source
	b.WriteString("\n")
	b.WriteString(labelStyle.Render(fmt.Sprintf("Source: %s", item.Source)))

	return detailBoxStyle.Render(b.String())
}

// RenderCompact renders a one-line summary
func (r *BaseRenderer) RenderCompact(item Item) string {
	icon := ""
	if item.Icon != "" {
		icon = item.Icon + " "
	}

	status := ""
	if item.Status != "" {
		status = fmt.Sprintf(" [%s]", item.Status)
	}

	return fmt.Sprintf("%s%s%s → %s", icon, item.Title, status, item.Description)
}

// renderDetails renders the Details map based on content
func (r *BaseRenderer) renderDetails(item Item) string {
	if len(item.Details) == 0 {
		return ""
	}

	var b strings.Builder
	b.WriteString("\n")

	// Common detail fields
	if examples, ok := item.Details["examples"].([]interface{}); ok {
		b.WriteString(headerStyle.Render("Examples:"))
		b.WriteString("\n")
		for i, ex := range examples {
			if exMap, ok := ex.(map[string]interface{}); ok {
				cmd := exMap["command"]
				desc := exMap["description"]
				b.WriteString(fmt.Sprintf("%d. %s\n", i+1, codeStyle.Render(fmt.Sprint(cmd))))
				if desc != nil {
					b.WriteString(fmt.Sprintf("   %s\n", desc))
				}
			}
		}
		b.WriteString("\n")
	}

	if steps, ok := item.Details["steps"].([]interface{}); ok {
		b.WriteString(headerStyle.Render("Steps:"))
		b.WriteString("\n")
		for i, step := range steps {
			if stepMap, ok := step.(map[string]interface{}); ok {
				key := stepMap["key"]
				desc := stepMap["description"]
				if key != nil && key != "" {
					b.WriteString(fmt.Sprintf("%d. %s: %s\n", i+1, keyStyle.Render(fmt.Sprint(key)), desc))
				} else {
					b.WriteString(fmt.Sprintf("%d. %s\n", i+1, desc))
				}
			}
		}
		b.WriteString("\n")
	}

	if notes, ok := item.Details["notes"].(string); ok && notes != "" {
		b.WriteString(headerStyle.Render("Notes:"))
		b.WriteString("\n")
		b.WriteString(notes)
		b.WriteString("\n\n")
	}

	if related, ok := item.Details["related"].([]string); ok && len(related) > 0 {
		b.WriteString(labelStyle.Render("Related: "))
		b.WriteString(strings.Join(related, ", "))
		b.WriteString("\n")
	}

	if exercises, ok := item.Details["exercises"].([]string); ok && len(exercises) > 0 {
		b.WriteString(headerStyle.Render("Practice Exercises:"))
		b.WriteString("\n")
		for _, ex := range exercises {
			b.WriteString(fmt.Sprintf("  • %s\n", ex))
		}
		b.WriteString("\n")
	}

	if progress, ok := item.Details["progress"].(map[string]interface{}); ok {
		b.WriteString(headerStyle.Render("Progress:"))
		b.WriteString("\n")
		if started, ok := progress["started"].(string); ok {
			b.WriteString(fmt.Sprintf("  Started: %s\n", started))
		}
		if confidence, ok := progress["confidence"].(string); ok {
			b.WriteString(fmt.Sprintf("  Confidence: %s\n", confidence))
		}
		b.WriteString("\n")
	}

	return b.String()
}

// RenderList renders multiple items as a list
func (r *BaseRenderer) RenderList(items []Item, title string) string {
	var b strings.Builder

	b.WriteString(titleStyle.Render(title))
	b.WriteString("\n\n")

	for i, item := range items {
		b.WriteString(fmt.Sprintf("%d. %s\n", i+1, r.RenderCompact(item)))
	}

	return b.String()
}

// RenderError renders an error message
func RenderError(err error) string {
	errorStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("196")).
		Bold(true)

	return errorStyle.Render(fmt.Sprintf("Error: %v", err))
}

// RenderSuccess renders a success message
func RenderSuccess(msg string) string {
	successStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("46")).
		Bold(true)

	return successStyle.Render(msg)
}
