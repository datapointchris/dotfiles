# Publishing Documentation to GitHub Pages

The dotfiles documentation is automatically published to GitHub Pages using GitHub Actions.

## Automatic Deployment

Every push to the `main` branch automatically triggers documentation deployment via GitHub Actions.

**Workflow**: `.github/workflows/ci.yml`

The workflow:

1. Checks out the repository
2. Sets up Python 3.x
3. Caches dependencies for faster builds
4. Installs mkdocs-material and mkdocstrings
5. Runs `mkdocs gh-deploy --force` to build and deploy to the `gh-pages` branch

**Published URL**: <https://datapointchris.github.io/dotfiles/>

## Manual Deployment

You can manually deploy documentation using the task command:

```bash
task docs:deploy
```

This runs `mkdocs gh-deploy --force` which builds the site and pushes to the `gh-pages` branch.

## Local Development

### Serve Locally

Preview documentation with live reload:

```bash
task docs:serve
```

This starts a local server at <http://localhost:8000> with automatic reloading when files change.

### Build Locally

Build the documentation without deploying:

```bash
task docs:build
```

This creates a `site/` directory with the built documentation. The `site/` directory is gitignored and should not be committed.

### Clean Built Files

Remove the built `site/` directory:

```bash
task docs:clean
```

## First-Time Setup

If you're setting up documentation deployment for the first time:

### 1. Install Dependencies

```bash
task docs:install
```

This installs:

- mkdocs-material (theme)
- mkdocstrings[python] (API documentation)

### 2. Configure GitHub Repository

Ensure your repository settings are configured for GitHub Pages:

1. Go to repository Settings → Pages
2. Set Source to "Deploy from a branch"
3. Select branch: `gh-pages`
4. Select folder: `/ (root)`

The `gh-pages` branch is automatically created and managed by the `mkdocs gh-deploy` command.

### 3. Test Locally

Before deploying, always test locally:

```bash
task docs:serve
```

Verify:

- ✅ All pages load without errors
- ✅ Navigation works correctly
- ✅ Internal links resolve
- ✅ Search functions
- ✅ Code blocks render properly
- ✅ Admonitions display correctly
- ✅ Mermaid diagrams render

### 4. Deploy

Once satisfied with local testing:

```bash
# Automatic: Push to main branch
git add .
git commit -m "docs: update documentation"
git push origin main

# Manual: Deploy immediately
task docs:deploy
```

## Documentation Tasks Reference

All documentation tasks are defined in `taskfiles/docs.yml`:

| Command | Description |
|---------|-------------|
| `task docs:serve` | Serve locally with live reload |
| `task docs:build` | Build documentation site |
| `task docs:deploy` | Manually deploy to GitHub Pages |
| `task docs:install` | Install documentation dependencies |
| `task docs:clean` | Clean built documentation |

## Troubleshooting

**"Permission denied" when deploying**

Ensure you have write access to the repository and that GitHub Actions has write permissions.

**"Module not found" errors**

Install documentation dependencies:

```bash
task docs:install
```

**Changes not appearing on GitHub Pages**

1. Check that the workflow ran successfully in the Actions tab
2. GitHub Pages can take 1-2 minutes to update after deployment
3. Try a hard refresh (Cmd+Shift+R on macOS, Ctrl+Shift+R on Linux/Windows)
4. Check the `gh-pages` branch was updated with `git log origin/gh-pages`

**Local server won't start**

1. Ensure port 8000 is not in use
2. Reinstall dependencies: `task docs:install`
3. Check for syntax errors in mkdocs.yml

## GitHub Actions Workflow

The deployment workflow is triggered by:

- Pushes to the `main` branch
- Manual workflow runs from the GitHub Actions tab

**Workflow file**: `.github/workflows/ci.yml`

To manually trigger the workflow:

1. Go to repository → Actions tab
2. Select "Deploy Documentation" workflow
3. Click "Run workflow" → Select branch → "Run workflow"

## Site Configuration

The site is configured in `mkdocs.yml`:

- **site_name**: Dotfiles
- **site_url**: <https://datapointchris.github.io/dotfiles/>
- **repo_url**: <https://github.com/datapointchris/dotfiles>
- **theme**: material (mkdocs-material)

The site URL is required for proper GitHub Pages deployment and correct link generation.

## Best Practices

**Before Committing Documentation Changes**:

1. ✅ Test locally with `task docs:serve`
2. ✅ Check all internal links work
3. ✅ Verify code examples are correct
4. ✅ Review for typos and formatting
5. ✅ Ensure admonitions use correct types
6. ✅ Test mermaid diagrams render properly

**When Adding New Pages**:

1. Create the markdown file in the appropriate directory
2. Add the page to `nav` section in `mkdocs.yml`
3. Test locally to ensure navigation works
4. Cross-link from related pages

**When Reorganizing Documentation**:

1. Update all internal links to use new paths
2. Test all links with local server
3. Update `nav` section in `mkdocs.yml`
4. Document the reorganization in `DOCS_REORGANIZATION_SUMMARY.md`

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Publishing to GitHub Pages](https://squidfunk.github.io/mkdocs-material/publishing-your-site/)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
