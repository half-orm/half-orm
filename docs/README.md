# halfORM Documentation

This directory contains the documentation for halfORM, built with MkDocs and supporting multiple versions via mike.

## Multi-version Setup

The documentation supports multiple versions:

- **Latest stable** (`latest`): Current stable release (e.g., 0.16.1)
- **Development** (`dev`): Development version from main branch
- **Release candidates** (`0.16.0-rc1`, etc.): Pre-release versions
- **Historical versions** (`0.15.0`, `0.14.0`, etc.): Previous releases

### URL Structure

- `https://half-orm.github.io/half-orm/` - Redirects to latest stable
- `https://half-orm.github.io/half-orm/latest/` - Latest stable version
- `https://half-orm.github.io/half-orm/dev/` - Development version
- `https://half-orm.github.io/half-orm/0.15.0/` - Specific version

## Local Development

### Prerequisites

```bash
pip install mkdocs-material mkdocstrings-python mkdocs-git-revision-date-localized-plugin mike
```

### Quick Start

1. **Build and serve current documentation:**
   ```bash
   mkdocs serve
   ```

2. **Deploy a version locally:**
   ```bash
   # Make the script executable
   chmod +x scripts/deploy-docs.sh
   
   # Deploy current version as development
   ./scripts/deploy-docs.sh deploy dev
   
   # Deploy a specific version
   ./scripts/deploy-docs.sh deploy 0.16.0 latest
   ```

3. **Serve multi-version documentation:**
   ```bash
   ./scripts/deploy-docs.sh serve
   ```

### Development Commands

```bash
# Build documentation
./scripts/deploy-docs.sh build

# List all versions
./scripts/deploy-docs.sh list

# Deploy development version
./scripts/deploy-docs.sh deploy dev

# Deploy release version
./scripts/deploy-docs.sh deploy 0.16.0 latest

# Set default version
./scripts/deploy-docs.sh set-default latest

# Delete a version
./scripts/deploy-docs.sh delete old-version
```

## Automatic Deployment

The documentation is automatically deployed via GitHub Actions:

### Triggers

- **Push to main**: Deploys as `dev` version
- **Push to release branches**: Deploys as release candidate
- **Git tags** (`v*`): Deploys as stable version with `latest` alias

### Workflow

1. **Development**: Push to `main` → deployed as `dev`
2. **Release candidate**: Push to `release/0.16.0` → deployed as `0.16.0-rc`
3. **Release**: Tag `v0.16.0` → deployed as `0.16.0` with `latest` alias

## Content Organization

### Version-specific Content

Some content may be version-specific. Use conditional blocks:

```markdown
{% if version == "0.16.0" %}
This feature is new in version 0.16.0.
{% endif %}

{% if version != "dev" %}
This applies to stable versions only.
{% endif %}
```

### Version Navigation

The version selector is automatically added to the top navigation. Users can switch between versions seamlessly.

## Content Guidelines

### Migration Information

When updating for a new version:

1. **Update version info** in `docs/index.md`
2. **Add migration guide** if breaking changes exist
3. **Update CLI examples** to reflect new commands
4. **Add new features** to relevant sections

### Cross-version Compatibility

- Keep URLs stable across versions when possible
- Use relative links for internal references
- Document breaking changes prominently
- Provide clear migration paths

## Release Process

### For Major Versions (0.16.0)

1. **Create release branch:**
   ```bash
   git checkout -b release/0.16.0
   ```

2. **Update documentation:**
   - Update version references
   - Add new features documentation
   - Update migration guides
   - Test locally

3. **Deploy release candidate:**
   ```bash
   git push origin release/0.16.0
   # This triggers RC deployment
   ```

4. **Create release tag:**
   ```bash
   git tag v0.16.0
   git push origin v0.16.0
   # This triggers stable deployment
   ```

### For Minor Versions (0.16.1)

1. **Update documentation on main**
2. **Create tag directly:**
   ```bash
   git tag v0.16.1
   git push origin v0.16.1
   ```

## Troubleshooting

### Local Issues

**Mike not found:**
```bash
pip install mike
```

**Permission errors:**
```bash
chmod +x scripts/deploy-docs.sh
```

**Version conflicts:**
```bash
# Clean up local versions
rm -rf .git/refs/heads/gh-pages
git branch -D gh-pages
```

### GitHub Actions Issues

- Check workflow logs in GitHub Actions tab
- Verify permissions are set correctly
- Ensure mike is installed in the workflow

## File Structure

```
docs/
├── index.md                    # Main documentation home
├── quick-start.md             # Quick start guide
├── guides/                    # How-to guides
├── api/                       # API reference
├── architecture/              # Architecture docs
├── examples/                  # Examples
├── ecosystem/                 # Ecosystem documentation
├── assets/                    # Static assets
└── README.md                  # This file

scripts/
└── deploy-docs.sh            # Local deployment script

mkdocs.yml                    # MkDocs configuration
.github/workflows/docs.yml    # GitHub Actions workflow
```

## Contributing

1. **For content changes:** Edit relevant `.md` files
2. **For structure changes:** Update `mkdocs.yml` navigation
3. **For styling:** Modify `docs/assets/css/custom.css`
4. **For workflow:** Update `.github/workflows/docs.yml`

Always test locally before pushing:

```bash
# Test current version
mkdocs serve

# Test multi-version setup
./scripts/deploy-docs.sh deploy dev
./scripts/deploy-docs.sh serve
```