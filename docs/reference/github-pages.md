# GitHub Pages Deployment

This documentation is deployed to GitHub Pages using mkdocs-material.

## The Real Problem

If you're seeing Jekyll errors, it's because GitHub Pages is configured incorrectly. The workflow is fine - you just need to change one setting.

## Solution: Configure GitHub Pages Source

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Pages**
3. Under **Build and deployment**:
   - **Source**: Select "Deploy from a branch"
   - **Branch**: Select `gh-pages` (NOT main)
   - **Folder**: Select `/ (root)`
4. Click **Save**

That's it. No other changes needed.

## How It Works

1. The workflow in `.github/workflows/ci.yml` runs on every push to `main`
2. It builds the mkdocs site using mkdocs-material
3. It pushes the built static site to the `gh-pages` branch
4. GitHub Pages serves the static files from `gh-pages`

mkdocs automatically includes a `.nojekyll` file in the `gh-pages` branch to prevent Jekyll processing.

## Common Error

**Error: "No such file or directory @ dir_chdir0 - /github/workspace/docs"**

This happens when GitHub Pages is trying to use Jekyll to build from the `main` branch + `/docs` folder. Jekyll is looking for files that don't exist because this project uses mkdocs, not Jekyll.

**Root Cause**: GitHub Pages source is set to "main branch" instead of "gh-pages branch"

**Fix**: Change the source to `gh-pages` branch as described above

## Manual Deployment

You can also deploy manually from your local machine:

```bash
task docs:deploy
```

This runs `mkdocs gh-deploy --force` which builds and deploys to the gh-pages branch.

## Workflow Configuration

The workflow has the necessary permissions already configured:

```yaml
permissions:
  contents: write
```

This allows the workflow to push to the `gh-pages` branch.
