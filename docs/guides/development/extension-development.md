# Getting Started with Extension Development

This guide walks you through creating your first halfORM extension that integrates with the unified `half_orm` command. You'll learn the basics of the extension system and build a simple but functional extension.

!!! info "Prerequisites"
    - Familiarity with Python packaging (`setup.py`, `pip install`)
    - Basic understanding of [Click](https://click.palletsprojects.com/) for command-line interfaces
    - Knowledge of halfORM fundamentals ([Quick Start](../../quick-start.md))
    - halfORM core installed (`pip install half_orm>=0.16.0`)

## What We'll Build

We'll create `half-orm-example`, a simple extension that demonstrates:

- Extension discovery and registration with the unified CLI
- Integration with `half_orm` commands
- Extension configuration and metadata
- Version compatibility checking

The final result will provide these commands:
```bash
half_orm example greet --name "World"     # Prints "Hello, World!"
half_orm example status                   # Shows extension information
```

!!! note "Real Example Available"
    For a complete working example, see [half-orm-test-extension](https://github.com/half-orm/half-orm-test-extension) which demonstrates all these concepts in production.

## Project Setup

### 1. Create Extension Project Structure

```bash
mkdir half-orm-example
cd half-orm-example

# Create the standard extension structure
mkdir -p half_orm_example
touch half_orm_example/__init__.py
touch half_orm_example/cli_extension.py  # Required: CLI integration
touch setup.py
touch README.md
touch requirements.txt
```

Your structure should look like:
```
half-orm-example/
├── half_orm_example/
│   ├── __init__.py
│   └── cli_extension.py    # Required: CLI integration
├── setup.py
├── requirements.txt
├── README.md
└── tests/                  # Optional but recommended
    └── test_extension.py
```

### 2. Package Configuration with Auto-Version Detection

Create `setup.py` with automatic halfORM version discovery:

```python
from setuptools import setup, find_packages

# Get halfORM version for compatibility
def get_half_orm_version():
    """Get half_orm version to ensure major.minor compatibility."""
    try:
        import half_orm
        version_parts = half_orm.__version__.split('.')
        # Use same major.minor, but allow independent patch versions
        return f"{version_parts[0]}.{version_parts[1]}.0"
    except ImportError:
        # Fallback if half_orm not installed during setup
        return "0.16.0"

VERSION = get_half_orm_version()

setup(
    name='half-orm-example',
    version=VERSION,
    description='Example extension for halfORM',
    long_description="""
# half-orm-example

A simple example extension demonstrating the halfORM ecosystem integration.

## Installation

`pip install half-orm-example`

## Usage

`half_orm example greet --name "World"`
`half_orm example status`

This extension provides basic commands to demonstrate the halfORM CLI integration system.
    """,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/half-orm-example',
    license='GPL-3.0',
    packages=find_packages(),
    install_requires=[
        f'half_orm>={VERSION.rsplit(".", 1)[0]}',  # Same major.minor
    ],
    extras_require={
        'dev': ['pytest', 'black', 'flake8'],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Database',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    python_requires='>=3.7',
)
```


## Core Extension Implementation

### 3. Extension Entry Point

Create `half_orm_example/cli_extension.py` - this is the **required** integration point:

```python
"""
CLI extension integration for half-orm-example

This module provides the entry point for the halfORM CLI extension system.
The add_commands() function is called automatically when the extension is discovered.
"""

import click

# Extension metadata for CLI discovery
EXTENSION_INFO = {
    'name': 'example',
    'description': 'Example extension demonstrating halfORM extension system',
    'version': '0.16.0',  # Should match halfORM major.minor
    'commands': ['greet', 'status'],
    'author': 'Your Name',
    'homepage': 'https://github.com/yourusername/half-orm-example',
    'license': 'GPL-3.0'
}


def pre_check(ctx):
    """
    Optional hook called before any command is resolved.

    Implement this function to run environment or precondition checks
    before halfORM searches for and executes any subcommand.  Raise a
    ``click.ClickException`` (or any exception) to abort with an error
    message; return normally to let execution continue.

    Args:
        ctx: The Click context of the top-level ``half_orm`` group.

    Examples:
        Check that the current directory is a halfORM project::

            from pathlib import Path
            if not Path('.half_orm').exists():
                raise click.ClickException(
                    "Not in a halfORM project directory. "
                    "Run 'half_orm dev new <project>' first."
                )
    """
    pass  # No preconditions for this example extension


def add_commands(cli_group):
    """
    Required entry point for halfORM extensions.
    
    This function is called automatically by half_orm's extension discovery system.
    It should add command groups to the main half_orm CLI.
    
    Args:
        cli_group: The main Click group for the half_orm command
    """
    
    @click.group(name='example')
    def extension_group():
        """Example extension commands"""
        pass
    
    @extension_group.command()
    @click.option('--name', default='halfORM', help='Name to greet')
    def greet(name):
        """Greet someone with a friendly message"""
        click.echo(f"Hello, {name}!")
    
    @extension_group.command()
    def status():
        """Show extension status and information"""
        click.echo("🔍 halfORM Example Extension Status")
        click.echo("=" * 35)
        click.echo(f"Extension name: {EXTENSION_INFO['name']}")
        click.echo(f"Version: {EXTENSION_INFO['version']}")
        click.echo(f"Description: {EXTENSION_INFO['description']}")
        click.echo(f"Commands: {', '.join(EXTENSION_INFO['commands'])}")
    
    # Register the command group with the main CLI
    cli_group.add_command(extension_group)
```

!!! tip "Le hook `pre_check` est optionnel"
    Si l'extension ne définit pas `pre_check`, le comportement est identique à avant : aucune vérification préalable n'est effectuée. Le hook ne sera appelé que si la fonction est présente dans le module `cli_extension`.

### 4. Extension Package Initialization

Update `half_orm_example/__init__.py`:

```python
"""
half-orm-example: An example extension for halfORM

This package demonstrates how to create extensions for the halfORM ecosystem.
"""

__version__ = '0.16.0'  # Should match halfORM major.minor
__author__ = 'Your Name'

# Import main functionality
from .cli_extension import EXTENSION_INFO

__all__ = ['EXTENSION_INFO']
```

### 5. Requirements File

Create `requirements.txt`:

```
half-orm>=0.16.0
pytest>=6.0  # For testing
```

## Extension Lifecycle Hooks

### `pre_check(ctx)` — precondition hook

halfORM automatically calls `pre_check(ctx)` **before any command is resolved**, for every extension that defines this function.

| Aspect | Detail |
|---|---|
| **When** | Before the CLI searches for and executes any subcommand |
| **Argument** | `ctx` — Click context of the top-level `half_orm` group |
| **To abort** | Raise a `click.ClickException` (displayed cleanly) or any other exception (automatically wrapped in a `ClickException`) |
| **To continue** | Return normally (`return` or `pass`) |
| **Optional** | Yes — extensions that do not define `pre_check` are unaffected |

**Typical use cases:**

- Check that the current directory is a valid halfORM project
- Verify the presence of a required configuration file
- Validate an environment variable required by the extension
- Check the availability of an external service

**Example — project directory check:**

```python
from pathlib import Path
import click

def pre_check(ctx):
    if not (Path.cwd() / '.half_orm').exists():
        raise click.ClickException(
            "Not in a halfORM project directory. "
            "Run 'half_orm dev new <project>' first."
        )
```

**Example — required environment variable:**

```python
import os
import click

def pre_check(ctx):
    if not os.environ.get('MY_EXT_API_KEY'):
        raise click.ClickException(
            "MY_EXT_API_KEY environment variable is not set."
        )
```

!!! warning "Performance"
    `pre_check` is called on every CLI invocation, including `half_orm --help`.
    Keep checks lightweight — avoid network calls or expensive I/O operations.