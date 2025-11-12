package registry

// Command represents a shell command, alias, or function
// Maps to commands.yml structure
type Command struct {
	Name        string   `yaml:"name"`
	Type        string   `yaml:"type"`        // alias, function, command
	Category    string   `yaml:"category"`    // "File Operations", "Git Workflows", etc.
	Description string   `yaml:"description"`
	Keywords    []string `yaml:"keywords"`
	Command     string   `yaml:"command"` // The actual command to run
	Examples    []Example `yaml:"examples,omitempty"`
	Notes       string   `yaml:"notes,omitempty"`
	Related     []string `yaml:"related,omitempty"`
	ProvidedBy  string   `yaml:"provided_by,omitempty"` // Tool that provides this command
	Platform    string   `yaml:"platform"` // all, macos, wsl
}

// Example represents a command usage example
type Example struct {
	Command     string `yaml:"command"`
	Description string `yaml:"description"`
}

// Workflow represents a multi-step process
// Maps to workflows.yml structure
type Workflow struct {
	Name        string       `yaml:"name"`
	Category    string       `yaml:"category"`
	Description string       `yaml:"description"`
	Keywords    []string     `yaml:"keywords"`
	Steps       []WorkflowStep `yaml:"steps"`
	Keybindings []Keybinding `yaml:"keybindings,omitempty"`
	Notes       string       `yaml:"notes,omitempty"`
	Resources   []Resource   `yaml:"resources,omitempty"`
	Platform    string       `yaml:"platform"`
}

// WorkflowStep represents a single step in a workflow
type WorkflowStep struct {
	Key         string `yaml:"key,omitempty"`
	Description string `yaml:"description"`
}

// Keybinding represents a keyboard shortcut
type Keybinding struct {
	Key         string `yaml:"key"`
	Description string `yaml:"description"`
}

// Resource represents a learning resource (bookmark, video, etc.)
type Resource struct {
	Type  string `yaml:"type"`  // bookmark, video, note
	Title string `yaml:"title"`
	URL   string `yaml:"url,omitempty"`
}

// LearningTopic represents an active learning topic
// Maps to learning.yml structure
type LearningTopic struct {
	Name         string   `yaml:"name"`
	Category     string   `yaml:"category"`
	Status       string   `yaml:"status"`       // active, completed, paused
	Description  string   `yaml:"description"`
	Keywords     []string `yaml:"keywords"`
	Progress     Progress `yaml:"progress"`
	Resources    LearningResources `yaml:"resources,omitempty"`
	Exercises    []string `yaml:"practice_exercises,omitempty"`
	RelatedFlows []string `yaml:"related_workflows,omitempty"`
	Platform     string   `yaml:"platform"`
}

// Progress tracks learning progress
type Progress struct {
	Started       string `yaml:"started"`
	LastPracticed string `yaml:"last_practiced"`
	Confidence    string `yaml:"confidence"` // beginner, intermediate, advanced
}

// LearningResources contains all resource types for a learning topic
type LearningResources struct {
	Bookmarks []Bookmark `yaml:"bookmarks,omitempty"`
	Notes     []Note     `yaml:"notes,omitempty"`
	Videos    []Video    `yaml:"videos,omitempty"`
}

// Bookmark represents a saved URL
type Bookmark struct {
	URL    string   `yaml:"url"`
	Title  string   `yaml:"title"`
	Tags   []string `yaml:"tags,omitempty"`
	Status string   `yaml:"status,omitempty"` // to-read, read, reference
}

// Note represents a linked note file
type Note struct {
	Path        string `yaml:"path"`
	Description string `yaml:"description"`
}

// Video represents a video resource
type Video struct {
	URL      string   `yaml:"url"`
	Title    string   `yaml:"title"`
	Tags     []string `yaml:"tags,omitempty"`
	Status   string   `yaml:"status,omitempty"` // to-watch, watched
	Duration string   `yaml:"duration,omitempty"`
}

// Root structures for each registry type
// These are what we unmarshal the YAML files into

// CommandsRegistry is the root structure for commands.yml
type CommandsRegistry struct {
	Commands []Command `yaml:"commands"`
}

// WorkflowsRegistry is the root structure for workflows.yml
type WorkflowsRegistry struct {
	Workflows []Workflow `yaml:"workflows"`
}

// LearningRegistry is the root structure for learning.yml
type LearningRegistry struct {
	Topics []LearningTopic `yaml:"learning"`
}

// MenuItem represents an item in the menu
// This is a unified type used by the UI
type MenuItem struct {
	Name        string
	Description string
	Category    string
	Type        string // command, workflow, learning
}

// ToMenuItem converts a Command to a MenuItem
func (c Command) ToMenuItem() MenuItem {
	return MenuItem{
		Name:        c.Name,
		Description: c.Description,
		Category:    c.Category,
		Type:        "command",
	}
}

// ToMenuItem converts a Workflow to a MenuItem
func (w Workflow) ToMenuItem() MenuItem {
	return MenuItem{
		Name:        w.Name,
		Description: w.Description,
		Category:    w.Category,
		Type:        "workflow",
	}
}

// ToMenuItem converts a LearningTopic to a MenuItem
func (l LearningTopic) ToMenuItem() MenuItem {
	status := ""
	if l.Status != "" {
		status = " [" + l.Status + "]"
	}
	return MenuItem{
		Name:        l.Name + status,
		Description: l.Description,
		Category:    l.Category,
		Type:        "learning",
	}
}
