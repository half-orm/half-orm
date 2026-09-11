# halfORM Extensions

halfORM 0.16 introduces a powerful extension system that automatically discovers and integrates additional functionality through the unified `half_orm` CLI.

## How Extensions Work

Extensions are Python packages that follow the `half-orm-*` naming convention and provide CLI integration through a simple discovery mechanism.

### Installation & Discovery

```bash
# Install any halfORM extension
pip install half-orm-extension-name

# Extensions are automatically discovered
half_orm --list-extensions

# Use extension commands immediately
half_orm extension-name command
```

### Extension Architecture

Extensions integrate seamlessly with the halfORM CLI by providing:

- **Auto-discovery**: Packages matching `half-orm-*` pattern
- **CLI integration**: Commands added to the main `half_orm` interface
- **Version compatibility**: Extensions must match halfORM core major.minor version

### Security Model

An extension is ordinary Python code that the CLI imports, so loading one is
running it. halfORM asks before doing that, and remembers what it ran.

- **Official extensions** — maintained by the halfORM team. Loaded without
  asking, but the build is recorded on first sight and checked afterwards.
- **Community extensions** — approved by you, per project. Approving one in
  a checkout does not approve it anywhere else.
- **Module ownership** — the module that gets imported must belong to the
  distribution that was checked. A directory of the right name earlier on
  `sys.path` does not inherit its verdict.
- **Version compatibility** — an extension you rely on must match the core
  `major.minor`; one you never approved is skipped rather than fatal.

```bash
# Approving a community extension: prompted on first use
half_orm my-extension command

# Forget an approval, or a recorded build
half_orm --untrust my-extension
```

#### Where trust is recorded

In `~/.config/half_orm/cli.json` — `%APPDATA%` on Windows, `$XDG_CONFIG_HOME`
when set — created `0600`. Deliberately outside your project: a checkout is
untrusted input, and one able to write its own approvals would grant itself
silent consent.

Set `HALF_ORM_CLI_CONFIG` to place the file elsewhere.

#### What an approval covers

A digest of the extension's code, not just its version number. Republishing
different code under the same version does not inherit the approval — you are
asked again, and told why.

The same applies to official extensions, which are skipped rather than loaded
when their content changes while their version does not:

```bash
# After reinstalling an extension at the same version
half_orm --untrust my-extension   # accepts the new build, everywhere
```

Editable installs (`pip install -e`) are not pinned. Their code is a working
tree meant to change between two commands, so approving one pins where it is
rather than what it contains.

#### Unattended runs

There is nobody to answer a prompt in CI, and an extension that quietly fails
to load turns its commands into "No such command". halfORM refuses instead,
with a non-zero exit:

```bash
export HALF_ORM_TRUST_EXTENSIONS=1   # load extensions without prompting
```

`--trusted-extensions` does the same on the command line.

## Available Extensions

### ✅ Official Extensions

#### half-orm-inspect
**Purpose**: Enhanced database inspection and exploration  
**Status**: In development

```bash
# When available
pip install half-orm-inspect

# Usage  
half_orm inspect my_database
half_orm inspect my_database public.users --details
```

### 🧪 Reference Extension

#### half-orm-test-extension
**Purpose**: Demonstration and testing of the extension system
**Repository**: [half-orm/half-orm-test-extension](https://github.com/half-orm/half-orm-test-extension)

Distributed through GitHub rather than PyPI, so it is approved like any
community extension: the allowlist grants trust by name, and a name nobody
has registered on PyPI is a name anyone can take.

```bash
# Installation
pip install git+https://github.com/half-orm/half-orm-test-extension

# Usage — prompts for approval the first time
half_orm test-extension greet --name "World"
half_orm test-extension status
```

### 📋 More Extensions in Development

Official extensions are maintained by the halfORM team and follow strict quality and compatibility standards. More extensions are in active development to support various use cases like API generation, admin interfaces, and monitoring tools.

## Creating Extensions

Building halfORM extensions is straightforward with the new simplified architecture:

### Simple Extension Template

```python
# your_extension/cli_extension.py
import sys
import click
from half_orm.cli_utils import create_and_register_extension

def add_commands(main_group):
    """Required entry point for halfORM extensions."""
    
    @create_and_register_extension(main_group, sys.modules[__name__])
    def your_extension():
        """Your extension description"""
        pass
    
    @your_extension.command()
    @click.option('--name', default='World', help='Name to greet')
    def hello(name):
        """Say hello command"""
        click.echo(f"Hello, {name}!")
    
    @your_extension.command()
    def status():
        """Show extension status"""
        from half_orm.cli_utils import get_package_metadata, get_extension_commands
        
        metadata = get_package_metadata(sys.modules[__name__])
        commands = get_extension_commands(your_extension)
        
        click.echo(f"Extension: {metadata['package_name']}")
        click.echo(f"Version: {metadata['version']}")
        click.echo(f"Commands: {', '.join(commands)}")
```

### Key Features

- **Auto-registration**: Use `@create_and_register_extension` decorator
- **Automatic metadata**: Version, description, and commands discovered automatically
- **Security model**: official extensions loaded without prompting but watched, community extensions approved per project
- **Version compatibility**: Must match halfORM core major.minor version

For a complete working example, see [half-orm-test-extension](https://github.com/half-orm/half-orm-test-extension) which demonstrates all the essential patterns.

## Development Resources

- **[Extension Development Guide](../guides/development/extension-development.md)** - Complete development tutorial
- **[halfORM Development Workflow](../guides/development/development-workflow.md)** - Core development process
- **[Documentation Workflow](../guides/development/documentation-workflow.md)** - Documentation standards

## Community and Support

- **[GitHub Discussions](https://github.com/half-orm/half-orm/discussions)** - Ask questions, share ideas
- **[GitHub Issues](https://github.com/half-orm/half-orm/issues)** - Report bugs, request features
- **[Extension Ideas](https://github.com/half-orm/half-orm/discussions/categories/ideas)** - Propose new extensions

---

**The halfORM extension system brings modular functionality to PostgreSQL development while maintaining security and compatibility.**

Ready to get started? **[Install halfORM →](../quick-start.md)** or **[Create your first extension →](../guides/development/extension-development.md)**