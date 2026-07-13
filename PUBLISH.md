# Publish to GitHub

The `easby-scripts` repository does not exist yet on GitHub. Create it once, then push.

## Option A — GitHub website

1. Open https://github.com/new
2. Repository name: `easby-scripts`
3. Visibility: Public (or Private)
4. Do **not** add README, `.gitignore`, or license
5. Create repository
6. From this folder, run:

```bash
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/pongsathonkheereekaew/easby-scripts.git
git push -u origin main
```

## Option B — GitHub CLI (on your Mac)

```bash
gh repo create pongsathonkheereekaew/easby-scripts --public --source=. --remote=origin --push
```

## Staging copy

This code is also available on branch `cursor/easby-scripts-video-web-download-6dfc` in `harness-flow` as a temporary mirror until `easby-scripts` is created.

```bash
git clone --branch cursor/easby-scripts-video-web-download-6dfc \
  https://github.com/pongsathonkheereekaew/harness-flow.git easby-scripts
cd easby-scripts
# then follow Option A step 6 to point at the new easby-scripts repo
```
