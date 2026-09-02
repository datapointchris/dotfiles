"""`python -m dotfiles.worktree`, which is what the fzf preview re-invokes.

The console script `[project.scripts]` declares is the door a person uses. This
one exists because a preview command has to name an interpreter and a module, and
a module inside a package cannot be run as a file path.
"""

import sys

from dotfiles.worktree.cli import main

if __name__ == '__main__':
    sys.exit(main())
