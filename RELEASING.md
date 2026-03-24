# Release Process

This document describes how Moirai releases are created and deployed.

---

## Branch Strategy

```
main                          ← stable, always releasable
 └── release/vX.Y.Z           ← collection branch for the next release
      ├── feat/some-feature    ← feature branches PR into here
      ├── feat/other-feature
      └── ...
```

- **Feature branches** target `release/vX.Y.Z` via PR. CI (pytest + Playwright + SonarCloud) runs on every PR.
- **`release/vX.Y.Z`** collects all features. CI also runs on pushes to this branch.
- **`main`** is updated only by merging a completed release branch.

---

## Creating a Release

### 1. Prepare the release branch

Ensure the release branch is up to date with any hotfixes that landed on `main` after it was cut:

```bash
git checkout release/vX.Y.Z
git rebase main          # absorb any hotfixes from main
git push --force-with-lease
```

Verify all CI checks pass on the release branch before proceeding.

### 2. Tag from the release branch

```bash
git checkout release/vX.Y.Z
git tag vX.Y.Z
git push origin vX.Y.Z
```

The `docker-release.yml` workflow triggers on `v*.*.*` tags and:
- Builds and pushes Docker images tagged `:X.Y.Z`, `:X.Y`, `:X`, and `:latest`
- Injects `APP_VERSION=X.Y.Z` and `BUILD_NUMBER=<run_number>` into the images

### 3. Fast-forward merge to main

Because the release branch was rebased onto main in step 1, this merge is a fast-forward — no merge commit, clean linear history:

```bash
git checkout main
git merge --ff-only release/vX.Y.Z
git push origin main
```

If `--ff-only` fails, go back to step 1 and rebase again.

### 4. Deploy to production

```bash
helm upgrade moirai-release helm/ \
  --namespace moirai-release \
  --reuse-values \
  --set api.image.tag=X.Y.Z \
  --set ui.image.tag=X.Y.Z \
  --set nginx.ingress.host=moirai.hlan.net
```

### 5. Update CHANGELOG.md and tag the release on GitHub

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(cat CHANGELOG_FRAGMENT.md)"
```

---

## Hotfixes

Hotfixes for the current production version go directly to `main`:

```bash
git checkout main
git checkout -b hotfix/description
# ... make fix, write tests ...
git push origin hotfix/description
gh pr create --base main --title "fix: ..."
```

After merging, tag the hotfix:

```bash
git checkout main && git pull
git tag vX.Y.Z+1
git push origin vX.Y.Z+1
```

Then rebase the active release branch onto the updated main:

```bash
git checkout release/vA.B.C
git rebase main
git push --force-with-lease
```

---

## CI Triggers

| Event | Branches | Jobs run |
|-------|----------|----------|
| Push / PR | `main`, `release/**` | pytest, ui-test (Playwright), SonarCloud |
| Tag push `v*.*.*` | any | docker-release (build + push images) |

---

## Version Numbering

`MAJOR.MINOR.PATCH` — semantic versioning:

- **PATCH** (X.Y.**Z**): hotfixes, no new features
- **MINOR** (X.**Y**.0): new features, backward compatible
- **MAJOR** (**X**.0.0): breaking changes

`APP_VERSION` in running containers comes from the image tag. `BUILD_NUMBER` is the GitHub Actions run number (local dev builds use a timestamp instead).
