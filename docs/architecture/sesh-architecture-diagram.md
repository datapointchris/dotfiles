# sesh Architecture Diagram

## High-Level Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ connect  │  │   list   │  │  clone   │  │ preview  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │              │             │              │
│       └─────────────┴──────────────┴─────────────┘              │
│                          │                                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    Core Business Logic                          │
│                          │                                      │
│  ┌───────────────────────▼────────────────────────┐            │
│  │            Connector (connect.go)              │            │
│  │  Strategy Pattern for connection sources:     │            │
│  │  1. tmuxStrategy                               │            │
│  │  2. tmuxinatorStrategy                         │            │
│  │  3. configStrategy                             │            │
│  │  4. dirStrategy                                │            │
│  │  5. zoxideStrategy                             │            │
│  └────────────┬───────────────────┬────────────────┘            │
│               │                   │                             │
│  ┌────────────▼─────┐   ┌─────────▼──────────┐                │
│  │     Lister       │   │      Namer         │                │
│  │  (list.go)       │   │   (namer.go)       │                │
│  │  - List sessions │   │   - Generate names │                │
│  │  - Hide dupes    │   │   - Git aware      │                │
│  │  - Sort results  │   │   - Shorten paths  │                │
│  └────────┬─────────┘   └────────────────────┘                │
└───────────┼──────────────────────────────────────────────────┘
            │
┌───────────┼──────────────────────────────────────────────────┐
│     External Resource Adapters                               │
│           │                                                  │
│  ┌────────▼─────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │     Tmux     │  │  Zoxide  │  │Tmuxinator│  │   Git   │ │
│  │              │  │          │  │          │  │         │ │
│  │ - List       │  │ - Query  │  │ - List   │  │ - Detect│ │
│  │ - NewSession │  │ - Add    │  │ - Load   │  │ - GetURL│ │
│  │ - Attach     │  │          │  │          │  │         │ │
│  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│         │               │             │             │       │
└─────────┼───────────────┼─────────────┼─────────────┼───────┘
          │               │             │             │
┌─────────┼───────────────┼─────────────┼─────────────┼───────┐
│    Infrastructure & Utilities                               │
│         │               │             │             │       │
│  ┌──────▼────┐   ┌──────▼────┐  ┌────▼─────┐  ┌────▼────┐ │
│  │   Shell   │   │Configurator│  │   Home   │  │   Dir   │ │
│  │  Wrapper  │   │ (TOML)     │  │  Utils   │  │  Utils  │ │
│  └─────┬─────┘   └────────────┘  └──────────┘  └─────────┘ │
│        │                                                    │
│  ┌─────▼─────┐   ┌──────────┐   ┌──────────┐              │
│  │ ExecWrap  │   │ OsWrap   │   │ PathWrap │              │
│  │ (os/exec) │   │ (os pkg) │   │ (path)   │              │
│  └───────────┘   └──────────┘   └──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## Dependency Injection Flow

```
main()
  │
  └─► NewRootCommand(version)
       │
       ├─► Create Wrappers
       │    ├─► execwrap.NewExec()
       │    ├─► oswrap.NewOs()
       │    ├─► pathwrap.NewPath()
       │    └─► runtimewrap.NewRunTime()
       │
       ├─► Create Base Dependencies
       │    ├─► home.NewHome(os)
       │    ├─► shell.NewShell(exec, home)
       │    ├─► json.NewJson()
       │    └─► replacer.NewReplacer()
       │
       ├─► Create Resource Adapters
       │    ├─► git.NewGit(shell)
       │    ├─► dir.NewDir(os, git, path)
       │    ├─► tmux.NewTmux(os, shell)
       │    ├─► zoxide.NewZoxide(shell)
       │    └─► tmuxinator.NewTmuxinator(shell)
       │
       ├─► Load Configuration
       │    └─► configurator.GetConfig()
       │
       ├─► Create Core Services
       │    ├─► lister.NewLister(config, home, tmux, zoxide, tmuxinator)
       │    ├─► namer.NewNamer(path, git, home, config)
       │    ├─► connector.NewConnector(config, dir, home, lister, namer, ...)
       │    ├─► previewer.NewPreviewer(lister, tmux, icon, dir, ...)
       │    └─► cloner.NewCloner(connector, git)
       │
       └─► Create Commands
            ├─► NewListCommand(icon, json, lister)
            ├─► NewConnectCommand(connector, icon, dir)
            ├─► NewCloneCommand(cloner)
            └─► NewPreviewCommand(previewer)
```

## Data Flow: "sesh connect my-project"

```
1. User Input
   │
   └─► CLI: sesh connect "my-project"
        │
        └─► ConnectCommand.Run()

2. Strategy Selection
   │
   └─► Connector.Connect("my-project")
        │
        ├─► Try tmuxStrategy
        │    └─► Lister.FindTmuxSession("my-project")
        │         └─► Tmux.ListSessions()
        │              └─► Shell.ListCmd("tmux", "list-sessions", ...)
        │                   └─► ExecWrap.Command().Output()
        │
        ├─► Try tmuxinatorStrategy (if not found)
        │    └─► Lister.FindTmuxinatorConfig("my-project")
        │         └─► Tmuxinator.List()
        │
        ├─► Try configStrategy (if not found)
        │    └─► Lister.FindConfigSession("my-project")
        │
        ├─► Try dirStrategy (if not found)
        │    └─► Dir.Exists("my-project")
        │
        └─► Try zoxideStrategy (if not found)
             └─► Lister.FindZoxideSession("my-project")
                  └─► Zoxide.Query("my-project")

3. Connection Execution
   │
   └─► connectToTmux(connection)  [or connectToTmuxinator]
        │
        ├─► Check if session exists
        │    └─► Tmux.ListSessions()
        │
        ├─► If not exists:
        │    ├─► Startup.Start(session)
        │    │    ├─► Tmux.NewSession(name, path)
        │    │    └─► Execute startup commands
        │    │         └─► Tmux.SendKeys(pane, command)
        │    │
        │    └─► Add to Zoxide (if configured)
        │         └─► Zoxide.Add(path)
        │
        └─► Attach to session
             └─► Tmux.SwitchOrAttach(name)
                  ├─► If inside tmux:
                  │    └─► Shell.Cmd("tmux", "switch-client", "-t", name)
                  │
                  └─► If outside tmux:
                       └─► Shell.Cmd("tmux", "attach-session", "-t", name)
```

## Configuration Loading Flow

```
ConfiguratorgetConfig()
  │
  ├─► 1. Locate config file
  │    └─► ~/.config/sesh/sesh.toml
  │
  ├─► 2. Read and parse main config
  │    ├─► os.ReadFile(configPath)
  │    └─► toml.Unmarshal(file, &config)
  │         ├─► If strict_mode: enable DisallowUnknownFields
  │         └─► Custom error handling for user-friendly messages
  │
  ├─► 3. Process imports (if any)
  │    └─► For each import path:
  │         ├─► Expand ~ to home directory
  │         ├─► Read import file
  │         ├─► toml.Unmarshal(importFile, &importConfig)
  │         └─► Append to main config.SessionConfigs
  │
  └─► 4. Apply defaults
       └─► If config.DirLength < 1: set to 1
```

## Testing Architecture

```
Production Code              Test Code
─────────────────            ─────────────────

┌──────────────┐             ┌──────────────┐
│ Tmux (iface) │◄────────────│ MockTmux     │
└──────┬───────┘             └──────────────┘
       │                            ▲
       │ implements                 │ generated by mockery
       ▼                            │
┌──────────────┐             ┌──────────────┐
│  RealTmux    │             │  tmux_test   │
│              │             │  - Setup     │
│ - Uses Shell │             │  - Expect    │
│ - Real impl  │             │  - Assert    │
└──────────────┘             └──────────────┘


Test Pattern (Table-Driven):

┌─────────────────────────────────────────┐
│ TestHideDuplicates(t *testing.T)        │
│                                         │
│  tests := []struct {                    │
│      name          string               │
│      input         []Session            │
│      expected      []Session            │
│  }{                                     │
│      {name: "case1", ...},              │
│      {name: "case2", ...},              │
│  }                                      │
│                                         │
│  for _, tt := range tests {             │
│      t.Run(tt.name, func(t *testing.T) {│
│          mockTmux.On("Method").Return() │
│          result := lister.List(...)     │
│          assert.Equal(tt.expected)      │
│      })                                 │
│  }                                      │
└─────────────────────────────────────────┘
```

## Package Dependency Graph

```
                    main.go
                       │
                       ▼
                   seshcli/
                   (CLI layer)
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    connector/      lister/      previewer/
   (strategies)   (aggregator)  (rendering)
         │             │             │
         └─────────────┼─────────────┘
                       │
         ┌─────────────┼─────────────┬──────────┐
         ▼             ▼             ▼          ▼
      tmux/        zoxide/      tmuxinator/   git/
    (adapters)    (adapters)   (adapters)  (adapters)
         │             │             │          │
         └─────────────┼─────────────┴──────────┘
                       │
         ┌─────────────┼─────────────┬──────────┐
         ▼             ▼             ▼          ▼
      shell/         home/         dir/      namer/
    (execution)   (path utils)  (fs utils) (naming)
         │             │             │          │
         └─────────────┼─────────────┴──────────┘
                       │
         ┌─────────────┼─────────────┬──────────┐
         ▼             ▼             ▼          ▼
    execwrap/      oswrap/      pathwrap/    model/
   (os/exec wrap) (os wrap)   (path wrap)  (types)
         │             │             │          │
         └─────────────┴─────────────┴──────────┘
                       │
                  Go stdlib
              (exec, os, path)

Legend:
  ─►  depends on
  │   vertical flow
```

## Interface Design Pattern

```
Every package follows this pattern:

┌─────────────────────────────────────────┐
│  package tmux                           │
│                                         │
│  // Interface (exported)                │
│  type Tmux interface {                  │
│      ListSessions() ([]*Session, error) │
│      NewSession(name string) error      │
│  }                                      │
│                                         │
│  // Implementation (exported)           │
│  type RealTmux struct {                 │
│      shell shell.Shell  // Injected    │
│      os    oswrap.Os    // Injected    │
│  }                                      │
│                                         │
│  // Constructor (exported)              │
│  func NewTmux(shell, os) Tmux {         │
│      return &RealTmux{shell, os}        │
│  }                                      │
│                                         │
│  // Methods (implementation)            │
│  func (t *RealTmux) ListSessions() {    │
│      output, _ := t.shell.Cmd(...)     │
│      return parse(output)               │
│  }                                      │
└─────────────────────────────────────────┘

Benefits:
  ✓ Testable (mock the interface)
  ✓ Flexible (swap implementations)
  ✓ Clear contracts (interface defines behavior)
  ✓ Dependency injection (explicit in constructor)
```

## Error Handling Strategy

```
┌─────────────────────────────────────────────────────┐
│  Error Propagation Chain                            │
│                                                     │
│  CLI Command                                        │
│      │                                              │
│      ├─► Connector.Connect()                        │
│      │      │                                       │
│      │      ├─► Strategy 1: try                     │
│      │      │      └─► error → log, continue        │
│      │      │                                       │
│      │      ├─► Strategy 2: try                     │
│      │      │      └─► error → log, continue        │
│      │      │                                       │
│      │      └─► No strategies succeeded             │
│      │           └─► fmt.Errorf("no connection...") │
│      │                                              │
│      └─► Command prints error and exits             │
│                                                     │
│  Special Cases:                                     │
│  ─────────────                                      │
│  • Config errors: ConfigError with .Human()         │
│  • Tmux "no server running": silently ignore        │
│  • Shell command failures: propagate with context   │
└─────────────────────────────────────────────────────┘

Custom Error Type Example:

type ConfigError struct {
    Err          string  // Machine-readable
    HumanDetails string  // User-friendly
}

func (ce *ConfigError) Error() string {
    return ce.Err
}

func (ce *ConfigError) Human() string {
    return ce.HumanDetails
}
```

## Key Design Principles

1. **Interface-First Design**
   - Every external dependency has an interface
   - Enables testing without real dependencies

2. **Explicit Dependency Injection**
   - Constructor functions take dependencies
   - No global state, no magic

3. **Layered Architecture**
   - CLI → Core Logic → Adapters → Infrastructure
   - Clear separation of concerns

4. **Strategy Pattern for Extensibility**
   - Multiple connection sources handled uniformly
   - Easy to add new sources

5. **Wrapper Pattern for Testability**
   - Stdlib packages wrapped in interfaces
   - Can mock file system, exec, etc.

6. **Configuration as Code**
   - TOML format for human-friendliness
   - Strict mode for catching typos
   - Import system for modularity

7. **Logging Strategy**
   - Structured JSON logging (slog)
   - Environment-based log levels
   - Daily rotated log files

8. **Error Handling**
   - Custom error types for user-facing messages
   - Error wrapping with context
   - Graceful degradation (try multiple strategies)
