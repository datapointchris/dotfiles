package testutil

import (
	"os"
	"path/filepath"
)

// CreateTempDir creates a temporary directory for testing
func CreateTempDir(t interface{ TempDir() string }) string {
	return t.TempDir()
}

// WriteYAMLFile writes YAML content to a file
func WriteYAMLFile(path string, content string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0644)
}

// SampleCommandsYAML returns sample commands.yml content
func SampleCommandsYAML() string {
	return `commands:
  - name: "ls"
    type: "system_tool"
    category: "File Operations"
    description: "List directory contents"
    keywords: ["list", "files", "directory"]
    command: "ls -la"
    platform: "all"
    examples:
      - command: "ls -la"
        description: "List all files with details"
      - command: "ls -lh"
        description: "List with human-readable sizes"

  - name: "ll"
    type: "alias"
    category: "File Operations"
    description: "Alias for ls -la"
    keywords: ["list", "files"]
    command: "ls -la"
    platform: "all"

  - name: "gitlog"
    type: "function"
    category: "Git Workflows"
    description: "Pretty git log"
    keywords: ["git", "log", "history"]
    command: "git log --oneline --graph"
    platform: "all"
    notes: "Shows a nice graph view of commits"
`
}

// SampleWorkflowsYAML returns sample workflows.yml content
func SampleWorkflowsYAML() string {
	return `workflows:
  - name: "Git Commit Workflow"
    category: "Git"
    description: "Standard git commit workflow"
    keywords: ["git", "commit", "workflow"]
    platform: "all"
    steps:
      - key: "ga"
        description: "Stage changes"
      - key: "gc"
        description: "Commit changes"
      - key: "gp"
        description: "Push to remote"

  - name: "Vim Edit Workflow"
    category: "Vim"
    description: "Edit and save in vim"
    keywords: ["vim", "edit", "save"]
    platform: "all"
    steps:
      - description: "Open file with vim"
      - description: "Make changes"
      - key: ":wq"
        description: "Save and quit"
`
}

// SampleLearningYAML returns sample learning.yml content
func SampleLearningYAML() string {
	return `learning:
  - name: "Go Testing"
    category: "Programming"
    status: "active"
    description: "Learning Go testing best practices"
    keywords: ["go", "testing", "tdd"]
    platform: "all"
    progress:
      started: "2024-01-01"
      confidence: "intermediate"
    practice_exercises:
      - "Write table-driven tests"
      - "Use testify for assertions"
    resources:
      bookmarks:
        - url: "https://go.dev/doc/tutorial/add-a-test"
          title: "Go Testing Tutorial"
          status: "read"
      notes:
        - path: "~/notes/go-testing.md"
          description: "My Go testing notes"

  - name: "Docker Basics"
    category: "DevOps"
    status: "planned"
    description: "Learn Docker fundamentals"
    keywords: ["docker", "containers"]
    platform: "all"
    progress:
      confidence: "beginner"
`
}

// SampleTaskfileYAML returns sample Taskfile.yml content
func SampleTaskfileYAML() string {
	return `version: "3"

tasks:
  build:
    desc: Build the project
    cmds:
      - go build -o bin/app ./cmd/app

  test:
    desc: Run tests
    cmds:
      - go test ./...

  clean:
    desc: Clean build artifacts
    cmds:
      - rm -rf bin/
`
}

// SampleToolsRegistry returns sample tools registry.yml content
func SampleToolsRegistry() string {
	return `tools:
  bat:
    category: "File Viewers"
    description: "A cat clone with syntax highlighting"
    installed_via: "homebrew"
    tags: ["file-viewer", "syntax-highlighting"]
    docs_url: "https://github.com/sharkdp/bat"
    examples:
      - cmd: "bat file.txt"
        desc: "View file with syntax highlighting"
      - cmd: "bat -A file.txt"
        desc: "Show all characters including whitespace"

  fzf:
    category: "Search Tools"
    description: "Fuzzy finder for the command line"
    installed_via: "homebrew"
    tags: ["fuzzy-finder", "search"]
    docs_url: "https://github.com/junegunn/fzf"
    examples:
      - cmd: "fzf"
        desc: "Interactive fuzzy search"
`
}

// MockSessionOutput returns mock output from session list command
func MockSessionOutput() string {
	return `● main (3 windows) /Users/test/project
⚙ dotfiles (tmuxinator) /Users/test/dotfiles
○ work (2 windows) /Users/test/work
`
}

// MockTaskOutput returns mock output from task --list-all command
func MockTaskOutput() string {
	return `task: Available tasks for this project:
* build:       Build the project
* clean:       Clean build artifacts
* test:        Run tests
`
}

// MockNbOutput returns mock output from nb list command
func MockNbOutput() string {
	return `[1] first-note.md "First Note Title"
[2] second-note.md "Second Note Title"
[3] folder/third-note.md "Third Note Title"
`
}

// MockBukuOutput returns mock JSON output from buku
func MockBukuOutput() string {
	return `[
  {
    "index": 1,
    "url": "https://golang.org",
    "title": "The Go Programming Language",
    "description": "Official Go website",
    "tags": "go,programming,language"
  },
  {
    "index": 2,
    "url": "https://github.com",
    "title": "GitHub",
    "description": "Code hosting platform",
    "tags": "git,github,code"
  }
]`
}
