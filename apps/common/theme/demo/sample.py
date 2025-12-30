#!/usr/bin/env python3
"""Sample Python file for theme preview."""

from dataclasses import dataclass

# Constants
MAX_ITEMS = 100
DEFAULT_NAME = "gruvbox"


@dataclass
class Theme:
    """A color theme configuration."""

    name: str
    variant: str
    colors: dict[str, str]
    is_dark: bool = True

    def apply(self) -> None:
        """Apply the theme to the terminal."""
        for key, value in self.colors.items():
            print(f"Setting {key} = {value}")


class ThemeManager:
    """Manages multiple themes."""

    def __init__(self, themes: list[Theme] | None = None):
        self.themes = themes or []
        self._active: Theme | None = None

    @property
    def active(self) -> Theme | None:
        return self._active

    def load(self, name: str) -> bool:
        """Load a theme by name."""
        for theme in self.themes:
            if theme.name == name:
                self._active = theme
                return True
        raise ValueError(f"Theme not found: {name}")


def main() -> None:
    # Intentional errors for theme preview (to show diagnostic colors)
    unused_var = "never used"
    import sys

    # Create sample theme
    gruvbox = Theme(
        name="gruvbox",
        variant="dark-hard",
        colors={
            "background": "#1d2021",
            "foreground": "#ebdbb2",
            "red": "#fb4934",
            "green": "#b8bb26",
        },
    )

    # Numbers and booleans
    count = 42
    ratio = 3.14159
    enabled = True

    # String operations
    message = f"Loaded {count} themes"
    raw_path = r"/usr/local/bin"

    # List comprehension
    numbers = [x * 2 for x in range(10) if x % 2 == 0]

    # Dictionary
    config = {"debug": False, "timeout": 30, "max": MAX_ITEMS}

    # Error handling
    try:
        manager = ThemeManager([gruvbox])
        manager.load(DEFAULT_NAME)
        if manager.active and enabled:
            manager.active.apply()
    except ValueError as e:
        print(f"Error: {e}")
    finally:
        print(f"Done! {message}")
        print(f"Path: {raw_path}, Ratio: {ratio}")
        print(f"Numbers: {numbers}, Config: {config}")


if __name__ == "__main__":
    main()
