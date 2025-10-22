# Examples

## Admonitions

!!! note "This should be a note"  

    - First thing

    - [ ] Second thing
    - [X] Third thing checked

??? warning "Collapsible block"

    This is a collapsible block of text.
    And another line right below it

## Code Blocks

``` py title="Project dataclass"
@dataclass
class Project:
    name: str
    directory: pathlib.Path
    url: str

    def __post_init__(self):
        self.directory = pathlib.Path(self.directory)
```

## Definition Lists

`projects-sync.py`

:   Sync all of the projects specified in the `coding-projects.db` database.  Will not overwrite remote changes and the operation is itempotent.
