# molten.nvim — interactive Python execution in Neovim

Requires: `uv tool install jupyter` (provides the python3 kernel)

## Kernel

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

# Operator + motion (composes with vim motions)
<leader>me ip     # evaluate inner paragraph (between blank lines)
<leader>me }      # evaluate to next blank line
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

## Cell-Based Workflow (.py with # %% markers)

```python
# Works in both Neovim (molten) and VS Code (Python extension)
# Use <leader>mc per cell, or <leader>me ip on any block

# %%
import httpx
from pathlib import Path
BASE_URL = "http://localhost:8000"

# %% Upload a file
file_path = Path("test-data/sample.csv")
with open(file_path, "rb") as f:
    resp = httpx.post(f"{BASE_URL}/api/upload",
                      files={"file": (file_path.name, f, "text/csv")})
print(resp.status_code, resp.json())

# %% Check the result
for item in httpx.get(f"{BASE_URL}/api/files").json():
    print(f"{item['id']}: {item['name']} ({item['size']} bytes)")
```

## Jupytext Conversion

```bash
jupytext --to py:percent notebook.ipynb   # .ipynb → .py with # %%
jupytext --to notebook script.py          # .py → .ipynb for sharing
python script.py                          # # %% markers are just comments
```
