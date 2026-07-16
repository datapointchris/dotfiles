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

1. The workflow in `.github/workflows/deploy-docs.yml` runs on pushes to `main` that touch `docs/**` or `mkdocs.yml`
2. It installs the project's uv-locked dependencies, then runs `mkdocs build --strict` to fail fast on broken links or nav
3. It force-pushes the built static site to the `gh-pages` branch via `mkdocs gh-deploy --force`
4. GitHub Pages serves the static files from `gh-pages`

A `concurrency` group serializes deploys, so two docs pushes in quick succession queue instead of racing each other's `gh-pages` force-push. This is the single source of docs deployment — do not add a second workflow that also pushes `gh-pages`, or the two will race and one will fail the ref-lock with `cannot lock ref 'refs/heads/gh-pages'`.

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

The workflow grants `contents: write` so `gh-deploy` can push to the `gh-pages` branch. See `.github/workflows/deploy-docs.yml` for the full definition.
