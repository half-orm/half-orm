# Documentation Workflow Guide

This guide explains how halfORM's documentation is managed with multi-version support, automated deployment, and coordinated with the [Development Workflow](development-workflow.md).

## Overview

halfORM uses a multi-version documentation system with automated deployment that mirrors the development workflow. Documentation is automatically built and deployed for different development stages.

!!! info "Development Coordination"
    This documentation workflow is tightly coordinated with the [Development Workflow](development-workflow.md). 
    The same branch structure and versioning strategy applies to both code and documentation.

## Branch Structure & Documentation Deployment

The documentation deployment follows the same branch structure as code development:

| Branch/Tag Pattern | Version Deployed | URL | Description |
|-------------------|------------------|-----|-------------|
| `main` | `dev` | `/dev/` | Latest development documentation |
| `dev/X.Y.x` | `X.Y.x-dev` | `/X.Y.x-dev/` | Patch development documentation |
| `release/X.Y.x` | `X.Y.x-rc` | `/X.Y.x-rc/` | Release candidate documentation |
| `vX.Y.Z` (tags) | `X.Y.Z` | `/X.Y.Z/` + `/latest/` | Stable release (becomes default) |

## URL Structure

```
https://half-orm.github.io/half-orm/
├── /                   # → Redirects to latest stable version
├── /latest/           # → Current stable version (alias)
├── /0.16.0/          # → Specific stable version
├── /0.16.x-rc/       # → Release candidate
├── /0.16.x-dev/      # → Development patches
└── /dev/             # → Main branch development
```

## Automatic Deployment

### GitHub Actions Integration

Documentation is automatically deployed via GitHub Actions when:

- **Push to `main`** → Deploys `dev` version
- **Push to `dev/X.Y.x`** → Deploys `X.Y.x-dev` version  
- **Push to `release/X.Y.x`** → Deploys `X.Y.x-rc` version
- **Tag `vX.Y.Z`** → Deploys `X.Y.Z` version with `latest` alias

### Workflow Configuration

The documentation workflow is configured in `.github/workflows/docs.yml`:

```yaml
name: Documentation
on:
  push:
    branches: [ main, 'release/*', 'dev/*' ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]
```

### Version Resolution

The workflow automatically determines the appropriate version and alias:

```bash
# Examples of automatic version resolution
dev/0.16.x     → 0.16.x-dev
release/0.16.x → 0.16.x-rc
v1.1.0         → 1.1, titled "1.1.0"
main           → dev
```

The `latest` alias goes to the highest released version, not to whichever tag
was pushed last: tagging a fix on a maintenance branch does not move it. The
title never says "(latest)" -- a title is fixed at deploy time while the alias
moves, so a title that claimed it would go on claiming it after the alias had
left.

### Deprecating a version line

A branch declares itself end-of-life by carrying a `.deprecated` file at its
root. Its documentation is then titled `0.17.11 (deprecated)` in the version
menu, and it can no longer take the `latest` alias.

```bash
git switch 0.17
echo "End of life since 2026-09. Upgrade to 1.1." > .deprecated
git commit -am "docs: mark 0.17 as deprecated" && git push
gh workflow run docs.yml --ref 0.17 -f version=0.17     # redeploy to show it
```

The file's contents are optional -- an empty file is enough to mark the line --
and are echoed in the workflow log when present.

The statement lives on the branch rather than in a list inside the workflow,
because a list there goes stale: `KEPT_VERSIONS` still read `0.17 0.18 dev`
after 1.0 and 1.1 had been released, and the cleanup step deletes whatever is
absent from it.

Deprecation is recorded in the title, unlike `latest`, because it only ever
moves one way. **Redeploy the line when you deprecate it** -- nothing rewrites
the titles of versions already published.

## Local Development

### Prerequisites

```bash
# Install dependencies
pip install mkdocs-material mkdocstrings-python mkdocs-git-revision-date-localized-plugin mike
```

### Local Testing

```bash
# Serve current documentation (single version)
mkdocs serve

# Deploy version locally for testing
./scripts/deploy-docs.sh deploy dev
./scripts/deploy-docs.sh deploy 0.16.0-rc latest

# Serve multi-version documentation
./scripts/deploy-docs.sh serve
```

### Local Version Management

```bash
# List deployed versions
./scripts/deploy-docs.sh list

# Deploy specific version
./scripts/deploy-docs.sh deploy 0.16.0 latest

# Set default version
./scripts/deploy-docs.sh set-default latest

# Delete version
./scripts/deploy-docs.sh delete 0.16.0-rc1

# Build documentation only
./scripts/deploy-docs.sh build
```

## Content Management

### Version-Specific Content

Use conditional blocks for version-specific content:

```markdown
{% if version == "0.16.0" %}
This feature is new in version 0.16.0.
{% endif %}

{% if version != "dev" %}
This applies to stable versions only.
{% endif %}
```

### Documentation Updates

When updating documentation:

1. **Update relevant sections** for the changes
2. **Test locally** with `mkdocs serve`
3. **Include version-specific notes** if needed
4. **Update migration guides** for breaking changes
5. **Verify all links** work correctly

### Cross-Version Compatibility

- Keep URLs stable across versions when possible
- Use relative links for internal references
- Document breaking changes prominently
- Provide clear migration paths

## Version Management

### Default Version

The default version is what users see when they visit the root URL (`/`). It's automatically set when:

- A tag with `latest` alias is deployed
- Manual override using `mike set-default`

```bash
# Set default version manually
mike set-default --push latest
```

### Version Lifecycle

```bash
# Development → Release Candidate → Stable
dev/0.16.x → release/0.16.x → v0.16.0
0.16.x-dev → 0.16.x-rc → 0.16.0 (latest)
```

### Cleanup

```bash
# Remove old development versions
mike delete --push 0.15.x-dev 0.14.x-dev

# Remove old release candidates  
mike delete --push 0.16.0-rc1 0.16.0-rc2

# Keep stable versions for reference
# 0.16.0, 0.15.0, etc. are kept for historical access
```

## Troubleshooting

### Common Issues

**Documentation not updating:**
- Check GitHub Actions logs in the Actions tab
- Verify push triggered the correct workflow
- Ensure branch/tag naming follows conventions

**Version conflicts:**
```bash
# Reset local gh-pages branch
git fetch origin
git checkout gh-pages
git reset --hard origin/gh-pages
```

**Site shows 404 or old version:**
```bash
# Set default version explicitly
mike set-default --push latest

# Or check what versions are deployed
mike list
```

**Local mike issues:**
```bash
# Clean local mike state
rm -rf .git/refs/heads/gh-pages
git branch -D gh-pages
git fetch origin gh-pages:gh-pages
```

### GitHub Pages Configuration

Ensure GitHub Pages is configured correctly:

1. Go to **Settings** → **Pages**
2. Set **Source** to "Deploy from a branch"
3. Set **Branch** to `gh-pages`
4. Set **Folder** to `/ (root)`

### Manual Deployment

If automatic deployment fails:

```bash
# Emergency manual deployment
mike deploy --push --update-aliases 0.16.0 latest
mike set-default --push latest

# Verify deployment
mike list
```

## Best Practices

### Content Guidelines

1. **Keep documentation synchronized** with code changes
2. **Use consistent formatting** across all versions
3. **Include version compatibility** information
4. **Provide working examples** for each version
5. **Test all links** before publishing

### Version Management

1. **Clean up old versions** regularly
2. **Keep stable versions** for historical reference
3. **Document version changes** in release notes
4. **Test deployed versions** after each release

### Workflow Coordination

1. **Update documentation** with code changes in the same branch
2. **Follow the same branch patterns** as code development
3. **Coordinate releases** between code and documentation
4. **Test locally** before pushing to shared branches

## Advanced Usage

### Custom Version Deployment

```bash
# Deploy custom version for testing
mike deploy --push feature-test
mike set-default --push feature-test

# Deploy with custom alias
mike deploy --push --update-aliases 0.16.0 stable
```

### Multiple Environment Support

```bash
# Deploy to staging (using different branch)
mike deploy --push --remote staging-origin staging

# Deploy to production (using main remote)
mike deploy --push --update-aliases 0.16.0 latest
```

### Version Archival

```bash
# Archive old versions by moving to archive alias
mike deploy --push --update-aliases 0.14.0 archive-0.14.0
mike delete --push 0.14.0
```

## Integration with Development Workflow

This documentation workflow is designed to work seamlessly with the [Development Workflow](development-workflow.md):

- **Branch synchronization**: Same branch names, same purposes
- **Version coordination**: Documentation versions match code versions  
- **Release coordination**: Documentation and code released together
- **Testing integration**: Documentation tested with each code change

For complete information about the development process, branch management, and release procedures, see the [Development Workflow Guide](development-workflow.md).

## Scripts Reference

The `scripts/deploy-docs.sh` script provides convenient commands:

```bash
# Available commands
./scripts/deploy-docs.sh deploy VERSION [ALIAS]
./scripts/deploy-docs.sh list
./scripts/deploy-docs.sh serve  
./scripts/deploy-docs.sh set-default VERSION
./scripts/deploy-docs.sh delete VERSION
./scripts/deploy-docs.sh build
./scripts/deploy-docs.sh help
```

See the script file for detailed usage and options.