# GitHub Pages Deployment

`.github/workflows/deploy-docs.yml` runs on pushes to `main` touching `docs/**`
or `mkdocs.yml`. It builds with `mkdocs build --strict`, so a broken internal
link or a nav entry pointing at a deleted file fails the deploy rather than
publishing a hole, then force-pushes the built site to `gh-pages` with
`mkdocs gh-deploy --force`. `task docs:deploy` does the same thing from a local
machine.

**Never add a second workflow that pushes `gh-pages`.** The existing one holds a
`concurrency` group precisely so two docs pushes queue instead of racing; a
second publisher sits outside that group, and the loser of the race dies with
`cannot lock ref 'refs/heads/gh-pages'`. If something else needs to publish,
extend this workflow rather than adding one.

Pages must be configured to deploy from the `gh-pages` branch, not from `main`
with a `/docs` folder. The symptom of the wrong setting is a Jekyll error —
`No such file or directory @ dir_chdir0 - /github/workspace/docs` — which is
Jekyll looking for a source tree that does not exist because this site is
mkdocs. mkdocs writes `.nojekyll` into `gh-pages` to keep Jekyll out of the
built output.
