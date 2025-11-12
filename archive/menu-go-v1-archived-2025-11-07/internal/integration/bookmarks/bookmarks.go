package bookmarks

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
)

// BookmarksIntegration integrates with buku (bookmark manager)
type BookmarksIntegration struct {
	bukuBinary string // Path to buku binary
}

// NewIntegration creates a new bookmarks integration
func NewIntegration(bukuBinary string) *BookmarksIntegration {
	if bukuBinary == "" {
		bukuBinary = "buku"
	}

	return &BookmarksIntegration{
		bukuBinary: bukuBinary,
	}
}

// Name returns the integration name
func (b *BookmarksIntegration) Name() string {
	return "bookmarks"
}

// Type returns the integration type
func (b *BookmarksIntegration) Type() integration.IntegrationType {
	return integration.TypeExternal
}

// Bookmark represents a bookmark from buku
type Bookmark struct {
	Index       int      `json:"index"`
	URL         string   `json:"url"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Tags        string   `json:"tags"`
}

// Load fetches all bookmarks from buku
func (b *BookmarksIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Use "buku --print --json" to get all bookmarks in JSON format
	cmd := exec.CommandContext(ctx, b.bukuBinary, "--print", "--json")
	output, err := cmd.CombinedOutput()
	if err != nil {
		// If buku doesn't exist or fails, return empty list
		return []integration.Item{}, nil
	}

	return b.parseBookmarks(output)
}

// parseBookmarks parses JSON output from buku
func (b *BookmarksIntegration) parseBookmarks(jsonData []byte) ([]integration.Item, error) {
	var bookmarks []Bookmark
	if err := json.Unmarshal(jsonData, &bookmarks); err != nil {
		return nil, fmt.Errorf("failed to parse bookmarks JSON: %w", err)
	}

	items := make([]integration.Item, 0, len(bookmarks))

	for _, bookmark := range bookmarks {
		// Parse tags
		tags := []string{"bookmark"}
		if bookmark.Tags != "" {
			tagList := strings.Split(bookmark.Tags, ",")
			for _, tag := range tagList {
				tag = strings.TrimSpace(tag)
				if tag != "" {
					tags = append(tags, tag)
				}
			}
		}

		// Determine category from tags
		category := "Bookmarks"
		if contains(tags, "dev") || contains(tags, "programming") {
			category = "Development"
		} else if contains(tags, "docs") || contains(tags, "documentation") {
			category = "Documentation"
		} else if contains(tags, "article") || contains(tags, "blog") {
			category = "Articles"
		} else if contains(tags, "tool") {
			category = "Tools"
		}

		// Create description
		description := bookmark.Description
		if description == "" {
			description = bookmark.URL
		}

		details := map[string]interface{}{
			"url":         bookmark.URL,
			"description": bookmark.Description,
			"tags":        tags,
		}

		items = append(items, integration.Item{
			ID:          fmt.Sprintf("%d", bookmark.Index),
			Title:       bookmark.Title,
			Description: description,
			Category:    category,
			Icon:        "🔖",
			Tags:        tags,
			Status:      "saved",
			Source:      "bookmarks",
			Executable:  true,
			Command:     fmt.Sprintf("open %s", bookmark.URL), // macOS
			IsInteractive: false,
			Details:     details,
		})
	}

	return items, nil
}

// Get retrieves a specific bookmark by index
func (b *BookmarksIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	// Use buku to get specific bookmark
	cmd := exec.CommandContext(ctx, b.bukuBinary, "--print", id, "--json")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("bookmark %q not found", id)
	}

	items, err := b.parseBookmarks(output)
	if err != nil {
		return nil, err
	}

	if len(items) == 0 {
		return nil, fmt.Errorf("bookmark %q not found", id)
	}

	return &items[0], nil
}

// Search searches bookmarks using buku's built-in search
func (b *BookmarksIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	// Use buku's search: "buku --sany query --json"
	cmd := exec.CommandContext(ctx, b.bukuBinary, "--sany", query, "--json")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return []integration.Item{}, nil
	}

	return b.parseBookmarks(output)
}

// SearchByTag searches bookmarks by tag
func (b *BookmarksIntegration) SearchByTag(ctx context.Context, tag string) ([]integration.Item, error) {
	// Use buku's tag search: "buku --stag tag --json"
	cmd := exec.CommandContext(ctx, b.bukuBinary, "--stag", tag, "--json")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return []integration.Item{}, nil
	}

	return b.parseBookmarks(output)
}

// Execute opens a bookmark in the browser
func (b *BookmarksIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("item %q is not executable", item.ID)
	}

	// Get the URL from details
	url, ok := item.Details["url"].(string)
	if !ok || url == "" {
		return "", fmt.Errorf("bookmark has no URL")
	}

	// Return command to open URL
	// This works on macOS, Linux would use "xdg-open"
	return fmt.Sprintf("open %s", url), nil
}

// SupportsExecution indicates that bookmarks can be opened
func (b *BookmarksIntegration) SupportsExecution() bool {
	return true
}

// Refresh reloads bookmarks from buku
func (b *BookmarksIntegration) Refresh(ctx context.Context) error {
	// Bookmarks are dynamic, so refresh is implicit on next Load
	return nil
}

// AddBookmark adds a new bookmark
func (b *BookmarksIntegration) AddBookmark(url, title, tags string) (string, error) {
	// Return command to add bookmark
	cmd := fmt.Sprintf("%s --add %s", b.bukuBinary, url)

	if title != "" {
		cmd += fmt.Sprintf(" --title '%s'", title)
	}

	if tags != "" {
		cmd += fmt.Sprintf(" --tags '%s'", tags)
	}

	return cmd, nil
}

// DeleteBookmark deletes a bookmark by ID
func (b *BookmarksIntegration) DeleteBookmark(id string) (string, error) {
	return fmt.Sprintf("%s --delete %s", b.bukuBinary, id), nil
}

// UpdateBookmark updates a bookmark
func (b *BookmarksIntegration) UpdateBookmark(id string, fields map[string]string) (string, error) {
	cmd := fmt.Sprintf("%s --update %s", b.bukuBinary, id)

	if title, ok := fields["title"]; ok && title != "" {
		cmd += fmt.Sprintf(" --title '%s'", title)
	}

	if tags, ok := fields["tags"]; ok && tags != "" {
		cmd += fmt.Sprintf(" --tags '%s'", tags)
	}

	if url, ok := fields["url"]; ok && url != "" {
		cmd += fmt.Sprintf(" --url '%s'", url)
	}

	return cmd, nil
}

// Helper function
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
