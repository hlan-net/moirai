# Release Process

This project keeps version strings in three places. Every release and release
candidate must update all of them together:

- `version.py`
- `ui/package.json`
- `helm/Chart.yaml` (both `version` and `appVersion`)

The safe order is always: edit -> commit -> tag -> push -> GitHub release.

## Release Candidate (example: v0.4.0-rc.11)

1) Bump versions to the rc version in all three files.

2) Commit the bump on the target branch (usually `main`).

```bash
git commit -am "release: 0.4.0-rc.11"
```

3) Tag the commit.

```bash
git tag v0.4.0-rc.11
```

4) Push the commit and tag.

```bash
git push origin main
git push origin v0.4.0-rc.11
```

5) Create the prerelease notes.

```bash
gh release create v0.4.0-rc.11 --generate-notes --prerelease
```

## Final Release (example: v0.4.0)

1) Bump versions to the final version in all three files.

2) Commit the bump.

```bash
git commit -am "release: 0.4.0"
```

3) Tag the commit.

```bash
git tag v0.4.0
```

4) Push the commit and tag.

```bash
git push origin main
git push origin v0.4.0
```

5) Create the release notes.

```bash
gh release create v0.4.0 --generate-notes
```

## Guardrails

- The tag must point to the version-bump commit.
- Do not create a GitHub release before the tag exists.
- If the order slips, fix the tag and then update the GitHub release.

## Verification

```bash
git show v0.4.0
gh release view v0.4.0 --json tagName,url
```

## If a Release Was Created Too Early

1) Tag the correct commit and force the tag update on the remote.

```bash
git tag -f v0.4.0
git push origin -f v0.4.0
```

2) Update the release notes if needed.

```bash
gh release edit v0.4.0 --notes "<updated notes>"
```
