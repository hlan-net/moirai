# Release Process

This document describes how Moirai releases are created and deployed.

---

## Branch Strategy

```
main                    ← always releasable; every release is a tag on main
 ├── feat/some-feature   ← feature and fix branches, PR into main
 ├── fix/some-bug
 └── release/X.Y.Z       ← short-lived: version bump + changelog only
```

- **Feature and fix branches** target `main` via PR and are squash-merged. CI (pytest, Playwright, formatting checks, SonarCloud, CodeQL) runs on every PR.
- **`release/X.Y.Z`** is a branch for the release PR only. It carries the version bump and the changelog, not features.
- **Tags** `vX.Y.Z` on `main` trigger the image build.

## Version Management

Every release updates these files together, in the release PR:

| File | What changes |
|---|---|
| `CHANGELOG.md` | A `## [vX.Y.Z] — YYYY-MM-DD` heading at the top, above the previous release. If an `[Unreleased / In Development]` heading is present, rename it; otherwise add the heading. Add entries for anything merged without one. |
| `helm/Chart.yaml` | `version` and `appVersion`. |
| `ui/package.json` | `version`. |
| `docs/readme.md` | The "Latest Version" line. |

`version.py` is not edited. It reads `APP_VERSION` and `BUILD_NUMBER` from `/etc/moirai/build-info`, which the image build writes from the git tag.

The lifecycle is: **release PR → merge → tag → image build → GitHub Release → deploy → verify**.

---

## Creating a Release

### 1. Open the release PR

```bash
git checkout main && git pull
git checkout -b release/X.Y.Z
# edit the four files listed above
git commit -am "release: X.Y.Z"
git push -u origin release/X.Y.Z
gh pr create --title "release: X.Y.Z"
```

Wait for CI and read the review comments before merging.

### 2. Merge and tag

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag must point at the squash-merged release commit on `main`.

### 3. Wait for the image build

The `docker-release.yml` workflow triggers on `v*.*.*` tags, runs the tests, and builds and pushes `ghcr.io/hlan-net/moirai` and `ghcr.io/hlan-net/moirai-ui` tagged `X.Y.Z`, `X.Y`, `X` and `latest`.

```bash
# The run for the tag appears a few seconds after the push; wait for it,
# then watch that run and fail if it fails.
until RUN_ID=$(gh run list --workflow docker-release.yml --branch vX.Y.Z \
    --limit 1 --json databaseId --jq '.[0].databaseId') && [ -n "$RUN_ID" ]; do
  sleep 5
done
gh run watch "$RUN_ID" --exit-status
```

`--branch vX.Y.Z` selects the run started by this tag, not an earlier release's. Do not continue until it has succeeded: a tag without images cannot be deployed.

### 4. Create the GitHub Release

```bash
gh release create vX.Y.Z --generate-notes --verify-tag
```

### 5. Deploy to Production

```bash
helm upgrade moirai-release helm/ \
  --namespace moirai-release \
  --reuse-values \
  --set api.image.tag=X.Y.Z \
  --set ui.image.tag=X.Y.Z
```

### 6. Verify

- The About page shows `Moirai vX.Y.Z (<build number>)`.
- Work through the "after deploy" items in the release PR and in the changelog entries of the release.

---

## Guardrails & Verification

- **Tag Alignment:** The tag must point exactly to the version-bump commit. Check with `git show vX.Y.Z`.
- **Order of Operations:** Never create a GitHub Release before the git tag is pushed and its image build has succeeded.
- **Every version gets a tag.** A release commit without a tag has no images (this happened to v0.10.1; its changes shipped in v0.10.2).

### Correcting Mistakes
If a release is created on the wrong commit:
1. Force-update the local tag: `git tag -f vX.Y.Z <correct-sha>`
2. Force-push the tag: `git push origin -f vX.Y.Z`
3. Edit the GitHub release if notes need updating: `gh release edit vX.Y.Z --notes "..."`

---

## Hotfixes

A hotfix follows the same flow with a PATCH version: the fix goes to `main` through a PR, then a release PR bumps the version.

```bash
git checkout main && git pull
git checkout -b fix/description
# ... make fix, write tests ...
git push -u origin fix/description
gh pr create --base main --title "fix: ..."
```

After it is merged, cut `X.Y.Z+1` as described under "Creating a Release".

---

## CI Triggers

| Event | Branches | Jobs run |
|-------|----------|----------|
| Push / PR | `main`, `release/**` | pytest, ui-test (Playwright), formatting checks, SonarCloud, CodeQL |
| Push | `main` | docker-dev (build + push `:main` and `:sha-<hash>` images) |
| Tag push `v*.*.*` | any | docker-release (tests, build + push release images) |

---

## Version Numbering

`MAJOR.MINOR.PATCH` — semantic versioning:

- **PATCH** (X.Y.**Z**): hotfixes, no new features
- **MINOR** (X.**Y**.0): new features, backward compatible
- **MAJOR** (**X**.0.0): breaking changes

`APP_VERSION` in running containers comes from the image tag. `BUILD_NUMBER` is the GitHub Actions run number (local dev builds use a timestamp instead).
