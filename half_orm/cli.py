#!/usr/bin/env python3
"""
halfORM unified command-line interface

Discovers and integrates all halfORM extensions into a single CLI.
Extensions are discovered automatically based on package naming convention.

Usage:
    half_orm --help                          # Show all available commands
    half_orm --list-extensions               # List all extensions
    half_orm --untrust my-extension          # Remove extension from trust
    half_orm inspect database               # Inspect database
"""

import functools
import importlib
import json
import os
import sys
import traceback

from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Modern import to replace pkg_resources
try:
    from importlib.metadata import distributions
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import distributions

import click

import half_orm
from half_orm import utils

DEBUG_EXTENSIONS = os.environ.get('HALF_ORM_DEBUG_EXTENSIONS', '').lower() in ('1', 'true', 'yes')


class CustomGroup(click.Group):
    """Custom Click Group that provides better error messages for unknown commands."""

    def resolve_command(self, ctx, args):
        """Override to show available commands when command not found."""
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as e:
            # Check if this is a "No such command" error
            if 'No such command' in str(e):
                cmd_name = args[0] if args else 'unknown'

                # Get available commands
                available = sorted(self.list_commands(ctx))

                if not available:
                    # No commands available, re-raise original error
                    raise

                # Build custom error message
                message = f"\n❌ No such command '{cmd_name}'.\n"
                message += f"\n{utils.Color.bold('Available commands:')}\n"

                for available_cmd_name in available:
                    cmd = self.get_command(ctx, available_cmd_name)
                    if cmd:
                        help_text = cmd.help or cmd.short_help or ""
                        first_line = help_text.split('\n')[0] if help_text else ""
                        message += f"  • {utils.Color.bold(available_cmd_name)}: {first_line}\n"

                # Add usage hint
                full_path = ctx.command_path
                message += f"\nTry {utils.Color.bold(f'{full_path} <command> --help')} for more information.\n"

                # Raise new UsageError with custom message
                raise click.UsageError(message, ctx=ctx) from e
            else:
                # Re-raise other UsageErrors as-is
                raise

# Global cache for extensions
_cached_extensions = None
_trust_extensions = False

# Liste des extensions officielles
OFFICIAL_EXTENSIONS = {
    'half_orm_test_extension',
    'half_orm_inspect',
    'half_orm_dev',
}

def get_config_file():
    """Get path to project-specific halfORM CLI configuration."""
    return Path.cwd() / '.half_orm_cli'

def load_cli_config():
    """Load project-specific CLI configuration."""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_cli_config(config):
    """Save project-specific CLI configuration."""
    config_file = get_config_file()
    try:
        config['last_updated'] = datetime.now().isoformat()
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except OSError:
        return False

def check_version_compatibility(extension_version: str, core_version: str) -> bool:
    """Check if extension version is compatible with core version (major.minor must match)."""
    try:
        ext_parts = extension_version.split('.')
        core_parts = core_version.split('.')

        if len(ext_parts) < 2 or len(core_parts) < 2:
            return False

        # Major.minor must match exactly, patch can differ
        return ext_parts[0] == core_parts[0] and ext_parts[1] == core_parts[1]
    except (ValueError, IndexError):
        return False

def warn_version_incompatibility(package_name: str, ext_version: str, core_version: str):
    """Warn about version incompatibility."""
    click.echo(f"❌ ERROR: '{package_name}' v{ext_version} is incompatible", err=True)
    click.echo(f"   halfORM core: v{core_version}", err=True)
    click.echo(f"   Extension must have same major.minor version", err=True)
    click.echo(f"   Expected: {'.'.join(core_version.split('.')[:2])}.x", err=True)
    sys.exit(1)

def is_official_extension(package_name):
    """Check if extension is official."""
    hyph_package_name = package_name.replace('-', '_')
    return package_name in OFFICIAL_EXTENSIONS or hyph_package_name in OFFICIAL_EXTENSIONS

def is_trusted_extension(package_name, current_version=None):
    """Check if specific version of extension is trusted."""
    config = load_cli_config()
    trusted_extensions = config.get('trusted_extensions', {})

    if package_name in trusted_extensions:
        trusted_version = trusted_extensions[package_name].get('version')
        return trusted_version == current_version

    return False

def add_trusted_extension(package_name, version):
    """Add specific version of extension to trusted list."""
    config = load_cli_config()
    trusted = config.get('trusted_extensions', {})

    trusted[package_name] = {
        'version': version,
        'trusted_at': datetime.now().isoformat()
    }

    config['trusted_extensions'] = trusted
    save_cli_config(config)

def remove_trusted_extension(package_name):
    """Remove extension from trusted list."""
    config = load_cli_config()
    trusted = config.get('trusted_extensions', {})

    if package_name in trusted:
        del trusted[package_name]
        config['trusted_extensions'] = trusted
        save_cli_config(config)
        return True
    return False

def warn_unofficial_extension(package_name, current_version):
    """Show warning for non-official extensions."""
    # Skip warning if global trust mode or already trusted
    if (_trust_extensions or
        is_trusted_extension(package_name, current_version) or
        is_official_extension(package_name.replace('-', '_'))):
        return

    click.echo(f"⚠️  WARNING: '{package_name}' v{current_version} is not official", err=True)
    click.echo("   This extension could execute arbitrary code.", err=True)
    click.echo()

    click.echo("Choose an option:")
    click.echo("  [y] Continue once")
    click.echo(f"  [t] Trust version {current_version}")
    click.echo("  [n] Cancel (default)")

    choice = click.prompt("Your choice", type=click.Choice(['y', 't', 'n']), default='n')

    if choice == 'n':
        click.echo("Extension loading cancelled.")
        sys.exit(1)
    elif choice == 't':
        add_trusted_extension(package_name, current_version)
        click.echo(f"✅ Trusted '{package_name}' v{current_version}")

def discover_extensions() -> Dict[str, Any]:
    """Discover all installed halfORM extensions."""
    global _cached_extensions

    # Return cached result if available
    if _cached_extensions is not None:
        return _cached_extensions

    core_version = half_orm.__version__
    extensions = {}

    for dist in distributions():
        try:
            package_name = dist.metadata.get('Name') or dist.metadata.get('name')
            if not package_name or not (
                package_name.startswith('half-orm-') or
                package_name.startswith('half_orm_')
            ):
                continue

            # Get extension version
            current_version = dist.version

            # Version compatibility check (applies to all extensions)
            if not check_version_compatibility(current_version, core_version):
                warn_version_incompatibility(package_name, current_version, core_version)

            # Security check for non-official extensions
            if not is_official_extension(package_name):
                warn_unofficial_extension(package_name, current_version)

            # Import extension
            module_name = package_name.replace('-', '_')
            extension_module = importlib.import_module(f'{module_name}.cli_extension')

            if hasattr(extension_module, 'add_commands'):
                # Use package name as key instead of derived name to avoid conflicts
                extension_key = package_name

                # Import the utility functions for consistent metadata extraction
                from .cli_utils import get_extension_name_from_module, get_package_metadata
                display_name = get_extension_name_from_module(module_name)
                pkg_metadata = get_package_metadata(extension_module)

                extensions[extension_key] = {
                    'module': extension_module,
                    'package_name': package_name,
                    'version': current_version,
                    'metadata': pkg_metadata,  # Use auto-discovered metadata
                    'display_name': display_name
                }

        except ImportError as exc:
            # Only show import errors if in debug mode or for official extensions
            if is_official_extension(package_name):
                click.echo(f"Warning: Could not load official extension {package_name}: {exc}", err=True)
            continue
        except Exception as exc:
            # Only show other errors if in debug mode or for official extensions
            if is_official_extension(package_name):
                click.echo(f"Warning: Error loading official extension {package_name}: {exc}", err=True)
            continue

    _cached_extensions = extensions
    return extensions

def get_extension_info(extensions: Dict[str, Any]) -> str:
    """Generate formatted information about discovered extensions."""
    if not extensions:
        return "No extensions installed"

    info = ["Available extensions:"]

    for ext_key, ext_data in sorted(extensions.items()):
        package_name = ext_data['package_name']
        version = ext_data['version']
        display_name = ext_data['display_name']
        description = ext_data['metadata'].get('description', 'No description')

        # Status
        if is_official_extension(package_name):
            status = "[OFFICIAL]"
        elif is_trusted_extension(package_name, version):
            status = "[TRUSTED]"
        else:
            status = "[UNOFFICIAL]"

        info.append(f"  • {display_name} v{version} {status}")
        info.append(f"    {description}")

        commands = ext_data['metadata'].get('commands', [])
        if commands:
            info.append(f"    Commands: {', '.join(commands)}")

        info.append("")

    return "\n".join(info)

@click.group(
    cls=CustomGroup,
    context_settings={'help_option_names': ['-h', '--help']},
    invoke_without_command=True
)
@click.version_option(version=half_orm.__version__, prog_name='halfORM')
@click.option('--list-extensions', is_flag=True, help='List all installed extensions')
@click.option('--untrust', metavar='EXTENSION', help='Remove extension from trusted list')
@click.option('--trusted-extensions', is_flag=True, help='Skip security warnings')
@click.pass_context
def main(ctx, list_extensions, untrust, trusted_extensions):
    """
    halfORM - PostgreSQL-native ORM and development tools

    This command provides access to halfORM core functionality and all
    installed extensions through a unified interface.

    \b
    Core CLI provides:
    • Extension discovery and management
    • Security (trust/untrust extensions)
    • Version information

    \b
    Install extensions for additional functionality:
    • pip install half-orm-inspect    # Database inspection
    • pip install half-orm-dev        # Development tools
    • pip install half-orm-api        # API generation
    """
    global _trust_extensions
    _trust_extensions = trusted_extensions

    if list_extensions:
        extensions = discover_extensions()
        click.echo(get_extension_info(extensions))
        ctx.exit(0)

    if untrust:
        # Validate extension name format
        if not untrust.startswith('half-orm-'):
            untrust = f'half-orm-{untrust}'

        if remove_trusted_extension(untrust):
            click.echo(f"✅ Removed '{untrust}' from trusted extensions")
        else:
            click.echo(f"'{untrust}' was not in trusted list")
        ctx.exit(0)

    # If no subcommand is invoked, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)

@main.command()
def version():
    """Show version information for halfORM and extensions."""
    click.echo(f"halfORM Core: {half_orm.__version__}")

    extensions = discover_extensions()
    if extensions:
        click.echo("\nInstalled Extensions:")
        for ext_key, ext_data in sorted(extensions.items()):
            package_name = ext_data['package_name']
            version_info = ext_data['version']
            display_name = ext_data['display_name']

            if is_official_extension(package_name):
                status = "[OFFICIAL]"
            elif is_trusted_extension(package_name, version_info):
                status = "[TRUSTED]"
            else:
                status = "[UNOFFICIAL]"

            click.echo(f"  {display_name}: {version_info} {status}")
    else:
        click.echo("\nNo extensions installed")
        click.echo("Try: pip install half-orm-inspect")

def safe_command_wrapper(func):
    """Wrap command to catch and display exceptions with full traceback."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except click.ClickException:
            # Re-raise Click exceptions (already handled)
            raise
        except Exception as e:
            # Catch unexpected errors and show traceback
            click.secho(f"\nUnexpected error: {e}", fg='red', err=True)
            click.secho("\nFull traceback:", fg='yellow', err=True)
            click.echo(traceback.format_exc(), err=True)
            raise click.ClickException(str(e))
    return wrapper

def register_extensions():
    """Discover and register all halfORM extensions."""
    extensions = discover_extensions()

    for ext_key, ext_data in extensions.items():
        try:
            # Create a temporary group to capture commands
            temp_group = click.Group()

            # Let extension add its commands to temp group
            ext_data['module'].add_commands(temp_group)

            # Wrap each command and add to main CLI
            for name, command in temp_group.commands.items():
                # Wrap the command callback with safe error handling
                if hasattr(command, 'callback') and command.callback:
                    command.callback = safe_command_wrapper(command.callback)

                # Add wrapped command to main CLI
                main.add_command(command, name=name)

        except Exception as e:
            display_name = ext_data['display_name']
            click.echo(utils.error(f"Warning: Failed to register {display_name}: {e}"), err=True)
            if DEBUG_EXTENSIONS:
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(f"Use `{utils.Color.bold('HALF_ORM_DEBUG_EXTENSIONS=1')} half_orm ...` to display the complete traceback.\n")
            continue

# Auto-register extensions when module is imported
register_extensions()

if __name__ == '__main__':
    main()