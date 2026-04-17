# molten.nvim — interactive Python execution in Neovim

Requires: `uv tool install jupyter` (provides the python3 kernel)

## Kernel Lifecycle

```bash
<leader>mp        # start python3 kernel (must do first)
<leader>mi        # start kernel (prompts for type — pyspark, etc.)
<leader>mq        # stop kernel
```

## Evaluating Code

```bash
# Single line
<leader>ml        # evaluate current line

# Visual selection
V (select lines)
<leader>mv        # evaluate selection

# Operator + motion (most powerful — composes with vim motions)
<leader>me ip     # evaluate inner paragraph (between blank lines)
<leader>me }      # evaluate to next blank line
<leader>me ap     # evaluate paragraph including surrounding whitespace
<leader>me 5j     # evaluate current line + 5 lines down

# Cell-based (requires # %% markers)
<leader>mc        # re-evaluate cell cursor is in
<leader>md        # delete cell output
```

## Output

```bash
<leader>mo        # show output window
<leader>mh        # hide output window
<leader>mw        # enter output window (scroll long output, q to exit)
```

## Notebook Import/Export

```bash
<leader>mx        # export outputs (saves to .ipynb metadata)
<leader>mI        # import outputs (load existing notebook outputs)
```

## Workflow: Exploratory Python in a .py File

```python
# Open any .py file, start kernel with <leader>mp
# Write code, evaluate with <leader>ml or select + <leader>mv
# No special markers needed — just write and evaluate

import pandas as pd

df = pd.read_csv("data.csv")      # <leader>ml to run
df.head()                          # <leader>ml to see output
df.describe()                      # <leader>ml — output appears as virtual text
```

## Workflow: Cell-Based Notebook (.py with # %% markers)

```python
# Works in both Neovim (molten) and VS Code (Python extension)

# %% [markdown]
# # API File Upload Test

# %%
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000"

# %% Upload a file
file_path = Path("test-data/sample.csv")
with open(file_path, "rb") as f:
    response = httpx.post(
        f"{BASE_URL}/api/upload",
        files={"file": (file_path.name, f, "text/csv")},
    )
print(response.status_code)
print(response.json())

# %% Check the result
result = httpx.get(f"{BASE_URL}/api/files")
for item in result.json():
    print(f"{item['id']}: {item['name']} ({item['size']} bytes)")

# %% Clean up
httpx.delete(f"{BASE_URL}/api/files/{result.json()[0]['id']}")
```

Use `<leader>mc` to run each cell, or `<leader>me ip` on any block.

## Tips

```bash
# Convert existing .ipynb to cell-based .py
jupytext --to py:percent notebook.ipynb

# Convert cell-based .py back to .ipynb (for sharing)
jupytext --to notebook script.py

# Run the .py file normally (# %% markers are just comments)
python script.py
```
