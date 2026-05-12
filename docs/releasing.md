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

## Version Management

Moirai tracks versions in three critical locations. Every release must update all of them together:

- `version.py`: Python-side versioning.
- `ui/package.json`: Frontend versioning.
- `helm/Chart.yaml`: Deployment versioning (both `version` and `appVersion`).

The standard lifecycle is: **Bump Versions -> Commit -> Tag -> Push -> GitHub Release -> Deploy**.

---

## Creating a Release

### 1. Prepare the release branch
Ensure the release branch is up to date with any hotfixes that landed on `main`:

```bash
git checkout release/vX.Y.Z
git rebase main
git push --force-with-lease
```

### 2. Version Bump & Tag
Bump the version strings in the files listed above, then commit and tag:

```bash
git commit -am "release: X.Y.Z"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

The `docker-release.yml` workflow triggers on `v*.*.*` tags to build and push images.

### 3. Fast-forward merge to main
Ensure a clean linear history by fast-forwarding `main`:

```bash
git checkout main
git merge --ff-only release/vX.Y.Z
git push origin main
```

### 4. Deploy to Production
Update the Helm release with the new image tags:

```bash
helm upgrade moirai-release helm/ \
  --namespace moirai-release \
  --reuse-values \
  --set api.image.tag=X.Y.Z \
  --set ui.image.tag=X.Y.Z
```

### 5. Create GitHub Release
```bash
gh release create vX.Y.Z --generate-notes
```

---

## Guardrails & Verification

- **Tag Alignment:** The tag must point exactly to the version-bump commit.
- **Order of Operations:** Never create a GitHub release before the git tag is pushed.
- **Verification:** Use `git show vX.Y.Z` to verify the commit content.

### Correcting Mistakes
If a release is created on the wrong commit:
1. Force-update the local tag: `git tag -f vX.Y.Z <correct-sha>`
2. Force-push the tag: `git push origin -f vX.Y.Z`
3. Edit the GitHub release if notes need updating: `gh release edit vX.Y.Z --notes "..."`

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
