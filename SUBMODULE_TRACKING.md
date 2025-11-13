# Submodule Tracking and CI Configuration

## Overview

This repository includes the `pubmedbert-handler` submodule, which requires proper configuration for CI/CD pipelines to successfully checkout the code.

## Submodule Details

**Submodule:** `pubmedbert-handler`
**Remote:** https://github.com/dmerrimon/ilana-pubmedbert-handler.git
**Branch:** `main`
**Current Commit:** `0de3c0fa2b44c45c50bb8be74c77c2d06d85d835`

## Submodule Tracking Strategy

### Local Development

To work with submodules locally:

```bash
# Clone repository with submodules
git clone --recursive https://github.com/dmerrimon/ilanalabs-add-in.git

# Or if already cloned without --recursive:
git submodule update --init --recursive

# To update submodule to latest remote commit:
cd pubmedbert-handler
git fetch origin
git checkout origin/main  # or specific commit SHA
cd ..
git add pubmedbert-handler
git commit -m "Update submodule pubmedbert-handler to <SHA>"
git push
```

### Updating Submodule Pointer

When the submodule repository (`ilana-pubmedbert-handler`) receives new commits, the parent repository's submodule pointer must be updated:

1. **Fetch latest from submodule remote:**
   ```bash
   cd pubmedbert-handler
   git fetch origin
   ```

2. **Checkout desired commit** (usually latest on main):
   ```bash
   git checkout <commit-sha>
   # or
   git checkout origin/main
   ```

3. **Commit the pointer update in parent repo:**
   ```bash
   cd ..
   git add pubmedbert-handler
   git commit -m "Update submodule pubmedbert-handler to <SHA>"
   git push
   ```

## CI/CD Configuration

### GitHub Actions

For GitHub Actions workflows, use `fetch-depth: 0` to ensure full git history is available for submodule checkout:

```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository with submodules
        uses: actions/checkout@v4
        with:
          submodules: 'recursive'
          fetch-depth: 0  # Important: Fetch full history for submodules

      - name: Update submodules to latest
        run: |
          git submodule update --init --recursive --remote
```

### Alternative: Specify Token for Private Submodules

If the submodule is private, you may need to provide authentication:

```yaml
- name: Checkout repository with submodules
  uses: actions/checkout@v4
  with:
    submodules: 'recursive'
    token: ${{ secrets.GH_PAT }}  # Personal Access Token with repo access
    fetch-depth: 0
```

### Render Deployment

For Render or other deployment platforms, ensure the build script includes submodule initialization:

```yaml
# render.yaml
services:
  - type: web
    name: ilana-api
    env: python
    buildCommand: |
      git submodule update --init --recursive
      pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
```

Or in a `build.sh` script:

```bash
#!/bin/bash
set -e

# Initialize submodules
git submodule update --init --recursive

# Install dependencies
pip install -r requirements.txt
```

## Common Issues and Solutions

### Issue: CI fails with "fatal: reference is not a tree"

**Cause:** The parent repo's submodule pointer references a commit that doesn't exist in the submodule's remote repository.

**Solution:** Update the submodule pointer to a valid commit from the remote:

```bash
cd pubmedbert-handler
git fetch origin
git checkout origin/main
cd ..
git add pubmedbert-handler
git commit -m "Fix submodule pointer to valid remote commit"
git push
```

### Issue: "Submodule path 'pubmedbert-handler': checked out <SHA> does not match index"

**Cause:** Local submodule is at a different commit than what the parent repo expects.

**Solution:** Sync the submodule:

```bash
git submodule update --init --recursive
```

### Issue: Shallow clone fails to find submodule commits

**Cause:** CI is using `fetch-depth: 1` (shallow clone) which doesn't include the commit referenced by the parent repo.

**Solution:** Use `fetch-depth: 0` in CI configuration to fetch full history:

```yaml
- uses: actions/checkout@v4
  with:
    submodules: 'recursive'
    fetch-depth: 0  # Fetch all history
```

## Maintenance Guidelines

1. **Keep submodule pointer current:** Regularly update the submodule pointer when new commits are pushed to the submodule repository.

2. **Test before pushing:** Always verify the submodule commit exists in the remote before updating the pointer:
   ```bash
   cd pubmedbert-handler
   git ls-remote origin <commit-sha>
   ```

3. **Document updates:** Include submodule changes in commit messages:
   ```
   Update submodule pubmedbert-handler to <short-sha>

   Changes:
   - Feature/fix description
   - Another change
   ```

4. **CI validation:** Ensure CI workflows successfully checkout and build with submodules before merging.

## Submodule Update History

| Date | Parent Commit | Submodule Commit | Description |
|------|---------------|------------------|-------------|
| 2024-11-12 | 957ca9e3 | 0de3c0f | Fix CI submodule checkout - updated to latest remote commit |
| 2024-11-12 | e938103f | 3c3f166 | Update hardcoded PubMedBERT endpoints to AWS |

## References

- [Git Submodules Documentation](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [GitHub Actions Checkout Documentation](https://github.com/actions/checkout)
- [Render Build Configuration](https://render.com/docs/deploy-hooks)

---

**Last Updated:** 2024-11-12
**Maintained By:** Development Team
