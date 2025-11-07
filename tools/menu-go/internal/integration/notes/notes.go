package notes

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/ichrisbirch/menu/internal/integration"
)

// NotesIntegration integrates with nb (note-taking tool)
// Can also work with plain directories of markdown files
type NotesIntegration struct {
	nbBinary   string // Path to nb binary
	notesDir   string // Directory containing notes
	useNb      bool   // Whether to use nb or plain file access
}

// NewIntegration creates a new notes integration
func NewIntegration(nbBinary, notesDir string) *NotesIntegration {
	if nbBinary == "" {
		nbBinary = "nb"
	}

	// Check if nb is available
	_, err := exec.LookPath(nbBinary)
	useNb := err == nil

	return &NotesIntegration{
		nbBinary: nbBinary,
		notesDir: notesDir,
		useNb:    useNb,
	}
}

// Name returns the integration name
func (n *NotesIntegration) Name() string {
	return "notes"
}

// Type returns the integration type
func (n *NotesIntegration) Type() integration.IntegrationType {
	return integration.TypeInteractive
}

// Load fetches all notes
func (n *NotesIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	if n.useNb {
		return n.loadFromNb(ctx)
	}
	return n.loadFromDirectory(ctx)
}

// loadFromNb uses nb to list notes
func (n *NotesIntegration) loadFromNb(ctx context.Context) ([]integration.Item, error) {
	// Use "nb list" to get all notes
	cmd := exec.CommandContext(ctx, n.nbBinary, "list", "--no-color", "--no-id")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return []integration.Item{}, nil
	}

	return n.parseNbList(string(output)), nil
}

// parseNbList parses output from "nb list"
// Expected format: "[123] Title of note"
func (n *NotesIntegration) parseNbList(output string) []integration.Item {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	items := make([]integration.Item, 0, len(lines))

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		item := n.parseNbLine(line)
		if item.ID != "" {
			items = append(items, item)
		}
	}

	return items
}

// parseNbLine parses a single line from nb list
func (n *NotesIntegration) parseNbLine(line string) integration.Item {
	// Expected format: "[123] filename.md Title of note"
	// Extract ID (number in brackets)
	var id, title, filename string

	// Find [number]
	if strings.HasPrefix(line, "[") {
		endBracket := strings.Index(line, "]")
		if endBracket > 0 {
			id = line[1:endBracket]
			line = strings.TrimSpace(line[endBracket+1:])
		}
	}

	// Remaining part is filename + title
	parts := strings.SplitN(line, " ", 2)
	if len(parts) > 0 {
		filename = parts[0]
		if len(parts) > 1 {
			title = parts[1]
		} else {
			// Use filename as title
			title = strings.TrimSuffix(filename, filepath.Ext(filename))
		}
	}

	if id == "" || title == "" {
		return integration.Item{}
	}

	// Determine category based on filename or tags
	category := "Notes"
	tags := []string{"note", "markdown"}

	// Check for common note types
	lowerTitle := strings.ToLower(title)
	if strings.Contains(lowerTitle, "todo") || strings.Contains(lowerTitle, "task") {
		category = "Tasks"
		tags = append(tags, "todo", "task")
	} else if strings.Contains(lowerTitle, "idea") {
		category = "Ideas"
		tags = append(tags, "idea")
	} else if strings.Contains(lowerTitle, "log") || strings.Contains(lowerTitle, "journal") {
		category = "Journal"
		tags = append(tags, "journal", "log")
	}

	return integration.Item{
		ID:          id,
		Title:       title,
		Description: filename,
		Category:    category,
		Icon:        "📝",
		Tags:        tags,
		Source:      "notes",
		Executable:  true,
		Command:     fmt.Sprintf("%s show %s", n.nbBinary, id),
		IsInteractive: true,
		Details: map[string]interface{}{
			"filename": filename,
		},
	}
}

// loadFromDirectory loads notes from a directory (without nb)
func (n *NotesIntegration) loadFromDirectory(ctx context.Context) ([]integration.Item, error) {
	if n.notesDir == "" {
		return []integration.Item{}, nil
	}

	// Use filepath.Glob to find markdown files
	pattern := filepath.Join(n.notesDir, "*.md")
	files, err := filepath.Glob(pattern)
	if err != nil {
		return nil, fmt.Errorf("failed to glob notes: %w", err)
	}

	items := make([]integration.Item, 0, len(files))

	for _, file := range files {
		basename := filepath.Base(file)
		title := strings.TrimSuffix(basename, filepath.Ext(basename))

		items = append(items, integration.Item{
			ID:          basename,
			Title:       title,
			Description: basename,
			Category:    "Notes",
			Icon:        "📝",
			Tags:        []string{"note", "markdown"},
			Source:      "notes",
			Executable:  true,
			Command:     fmt.Sprintf("$EDITOR %s", file),
			IsInteractive: true,
			Details: map[string]interface{}{
				"path": file,
			},
		})
	}

	return items, nil
}

// Get retrieves a specific note by ID
func (n *NotesIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	items, err := n.Load(ctx)
	if err != nil {
		return nil, err
	}

	for _, item := range items {
		if item.ID == id {
			return &item, nil
		}
	}

	return nil, fmt.Errorf("note %q not found", id)
}

// Search filters notes by query
func (n *NotesIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	if n.useNb {
		// Use nb's built-in search
		return n.searchWithNb(ctx, query)
	}

	// Fallback to simple title search
	items, err := n.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// searchWithNb uses nb's search functionality
func (n *NotesIntegration) searchWithNb(ctx context.Context, query string) ([]integration.Item, error) {
	cmd := exec.CommandContext(ctx, n.nbBinary, "search", query, "--no-color")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return []integration.Item{}, nil
	}

	return n.parseNbList(string(output)), nil
}

// Execute opens a note for viewing or editing
func (n *NotesIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("item %q is not executable", item.ID)
	}

	return item.Command, nil
}

// SupportsExecution indicates that notes can be opened
func (n *NotesIntegration) SupportsExecution() bool {
	return true
}

// Refresh reloads notes
func (n *NotesIntegration) Refresh(ctx context.Context) error {
	// Notes are dynamic, so refresh is implicit on next Load
	return nil
}

// CreateNote creates a new note (if nb is available)
func (n *NotesIntegration) CreateNote(title string) (string, error) {
	if !n.useNb {
		return "", fmt.Errorf("nb not available for creating notes")
	}

	// Return command to create a new note
	return fmt.Sprintf("%s add --title '%s'", n.nbBinary, title), nil
}

// QuickCapture creates a quick note with timestamp
func (n *NotesIntegration) QuickCapture(content string) (string, error) {
	if !n.useNb {
		return "", fmt.Errorf("nb not available for quick capture")
	}

	timestamp := time.Now().Format("2006-01-02-150405")
	title := fmt.Sprintf("quick-%s", timestamp)

	return fmt.Sprintf("%s add --title '%s' --content '%s'", n.nbBinary, title, content), nil
}
