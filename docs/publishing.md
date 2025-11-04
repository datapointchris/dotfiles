# Publishing Docs

Documentation is automatically published to GitHub Pages.

## Automatic Deployment

Every push to `main` triggers deployment via GitHub Actions.

**Workflow**: `.github/workflows/ci.yml`

Published at: <https://datapointchris.github.io/dotfiles/>

## Manual Deployment

```sh
task docs:deploy
```

## Local Development

**Serve locally** (with live reload):

```sh
task docs:serve
```

Opens at <http://localhost:8000>

**Build without deploying**:

```sh
task docs:build
```

Creates `site/` directory (gitignored).

**Clean built files**:

```sh
task docs:clean
```

## First-Time Setup

**Install dependencies**:

```sh
task docs:install
```

**Configure GitHub Pages**:

1. Go to Settings → Pages
2. Source: "Deploy from a branch"
3. Branch: `gh-pages`
4. Folder: `/ (root)`

**Test before deploying**:

```sh
task docs:serve
```

Verify pages load, navigation works, links resolve, search functions.

## Troubleshooting

**Permission denied**: Check repo write access and Actions permissions

**Module not found**: Run `task docs:install`

**Changes not appearing**: Check Actions tab, wait 1-2 minutes, hard refresh

**Port 8000 in use**: Kill process or specify different port in mkdocs.yml

## Configuration

Site configured in `mkdocs.yml`:

- site_name: Dotfiles
- site_url: <https://datapointchris.github.io/dotfiles/>
- theme: material

See [MkDocs Material docs](https://squidfunk.github.io/mkdocs-material/) for customization.
