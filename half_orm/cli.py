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
import importlib.util
import json
import os
import sys
import traceback

from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from urllib.parse import unquote, urlparse

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

    def list_commands(self, ctx):
        """Override to register extension commands before listing them."""
        _ensure_extensions_registered()
        return super().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        """Override to register extension commands before looking one up."""
        _ensure_extensions_registered()
        return super().get_command(ctx, cmd_name)

    def resolve_command(self, ctx, args):
        """Override to show available commands when command not found."""
        _ensure_extensions_registered()
        extensions = discover_extensions()
        for ext_data in extensions.values():
            pre_check = ext_data.get('pre_check')
            if pre_check is not None:
                try:
                    pre_check(ctx)
                except (click.ClickException, SystemExit):
                    raise
                except Exception as e:
                    raise click.ClickException(str(e))

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

# Skipping the security prompt has to be expressible without a terminal, for
# CI and other unattended runs; the command-line flag alone cannot serve there.
TRUST_EXTENSIONS_ENV = 'HALF_ORM_TRUST_EXTENSIONS'

# Global cache for extensions
_cached_extensions = None
_trust_extensions = os.environ.get(TRUST_EXTENSIONS_ENV, '').lower() in ('1', 'true', 'yes')
_extensions_registered = False

def _set_trust_extensions(ctx, param, value):
    """Record --trusted-extensions as click parses it.

    Eager, and handled here rather than in the group callback, because --help
    is eager too: it renders the command list, which loads extensions. Read
    any later, the flag would arrive after the warnings it is meant to skip.
    An absent flag must not clear the environment variable.

    Click orders eager options by their position on the command line, so
    `--help --trusted-extensions` still resolves help first and refuses. That
    fails closed, which is the acceptable direction; TRUST_EXTENSIONS_ENV
    covers the case where order cannot be relied upon.
    """
    global _trust_extensions
    if value:
        _trust_extensions = True
    return value

# Extensions trusted without asking. Every name here must be a project the
# halfORM maintainers actually own on PyPI: an unclaimed name on this list is
# a free pass for whoever registers it first.
OFFICIAL_EXTENSIONS = {
    'half_orm_inspect',
    'half_orm_dev',
    'half_orm_gen'
}

# Pre-1.0 trust store, kept only to warn that it is no longer honoured.
LEGACY_CONFIG_NAME = '.half_orm_cli'

# Directory entries that mark the root of a project.
PROJECT_MARKERS = ('.hop', '.git')

_legacy_config_warned = False

def get_config_file():
    """Get path to the per-user halfORM CLI configuration.

    This file holds the extension trust store, which suppresses the security
    prompt raised for unofficial extensions. It therefore lives outside any
    project directory: a checkout is untrusted input, and a repository able to
    write its own trust store would silently grant itself consent.

    Honours HALF_ORM_CLI_CONFIG, then the platform's per-user configuration
    directory: %APPDATA% on Windows, $XDG_CONFIG_HOME (default ~/.config)
    elsewhere. Both live inside the user's profile, which is what keeps the
    file confidential -- the explicit 0600 applied on save is a Unix-only
    reinforcement, where a permissive umask could otherwise widen it.
    """
    override = os.environ.get('HALF_ORM_CLI_CONFIG')
    if override:
        return Path(override).expanduser()

    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA')
        base = Path(appdata) if appdata else Path.home() / 'AppData' / 'Roaming'
    else:
        xdg = os.environ.get('XDG_CONFIG_HOME')
        base = Path(xdg).expanduser() if xdg else Path.home() / '.config'
    return base / 'half_orm' / 'cli.json'

def get_project_key(start=None):
    """Identify the project a trust decision applies to.

    Walks up from `start` (default: the current directory) to the nearest
    project marker, so that running a command from a subdirectory reuses the
    decision already recorded for the project instead of asking again -- a
    prompt that keeps reappearing is a prompt that gets answered unread.
    """
    try:
        current = Path(start) if start else Path.cwd()
        current = current.resolve()
    except OSError:
        return os.path.normcase(str(start or ''))

    for directory in (current, *current.parents):
        for marker in PROJECT_MARKERS:
            if (directory / marker).exists():
                return os.path.normcase(str(directory))
    # normcase is a no-op on POSIX; on Windows it keeps C:\Proj and c:\proj
    # from becoming two separate trust scopes for one directory.
    return os.path.normcase(str(current))

def _warn_legacy_config():
    """Warn once that a pre-1.0 project-local trust store is being ignored."""
    global _legacy_config_warned
    if _legacy_config_warned:
        return
    _legacy_config_warned = True

    try:
        legacy = Path.cwd() / LEGACY_CONFIG_NAME
        if not legacy.exists():
            return
    except OSError:
        return

    click.echo(
        f"⚠️  Ignoring '{legacy}': extension trust is no longer read from the "
        "project directory, where a checkout could grant itself consent.",
        err=True)
    click.echo(f"   Trust is now recorded in {get_config_file()}", err=True)

def load_cli_config():
    """Load the per-user CLI configuration."""
    _warn_legacy_config()
    try:
        with open(get_config_file(), 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return config if isinstance(config, dict) else {}

def save_cli_config(config):
    """Save the per-user CLI configuration, readable by its owner only."""
    config_file = get_config_file()
    try:
        config_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        config['last_updated'] = datetime.now().isoformat()
        fd = os.open(config_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(config, f, indent=2)
        # O_CREAT only applies the mode on creation; an existing file keeps its
        # own, so narrow it explicitly. On Windows this only clears the
        # read-only flag, and confidentiality comes from the profile ACL.
        os.chmod(config_file, 0o600)
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

def _trusted_for_project(config, project_key):
    """Return the trust entries recorded for one project.

    Tolerates a malformed store rather than raising: a corrupt file must not
    break the CLI, and every shape it can take here means "not trusted".
    """
    trusted = config.get('trusted_extensions')
    if not isinstance(trusted, dict):
        return {}
    entries = trusted.get(project_key)
    return entries if isinstance(entries, dict) else {}

def is_trusted_extension(package_name, current_version=None):
    """Check if this version of an extension is trusted for this project."""
    entries = _trusted_for_project(load_cli_config(), get_project_key())
    entry = entries.get(package_name)
    if not isinstance(entry, dict):
        return False
    return entry.get('version') == current_version

def add_trusted_extension(package_name, version):
    """Trust a specific version of an extension, for this project only."""
    config = load_cli_config()
    project_key = get_project_key()

    trusted = config.get('trusted_extensions')
    if not isinstance(trusted, dict):
        trusted = {}
    entries = dict(_trusted_for_project(config, project_key))
    entries[package_name] = {
        'version': version,
        'trusted_at': datetime.now().isoformat()
    }

    trusted[project_key] = entries
    config['trusted_extensions'] = trusted
    save_cli_config(config)

def remove_trusted_extension(package_name):
    """Remove an extension from this project's trusted list."""
    config = load_cli_config()
    project_key = get_project_key()
    entries = dict(_trusted_for_project(config, project_key))

    if package_name not in entries:
        return False

    del entries[package_name]
    config['trusted_extensions'][project_key] = entries
    save_cli_config(config)
    return True

def _stdin_is_interactive():
    """Whether a human can answer a prompt on stdin.

    sys.stdin is None under pythonw, and closed streams raise on isatty().
    """
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False

def warn_unofficial_extension(package_name, current_version, provenance=None):
    """Show warning for non-official extensions."""
    # Skip warning if global trust mode or already trusted
    if (_trust_extensions or
        is_trusted_extension(package_name, current_version) or
        is_official_extension(package_name.replace('-', '_'))):
        return

    click.echo(f"⚠️  WARNING: '{package_name}' v{current_version} is not official", err=True)
    click.echo("   This extension could execute arbitrary code.", err=True)
    for line in provenance or ():
        click.echo(line, err=True)
    click.echo()

    if not _stdin_is_interactive():
        # Nobody is there to answer. Refusing out loud beats the two silent
        # outcomes: loading the extension unasked, or dropping it without a
        # word -- which is what happened while click.Abort, a RuntimeError,
        # was being swallowed by the caller's `except Exception: continue`.
        click.echo("   Refusing to load it: no terminal is attached to confirm.", err=True)
        click.echo("   Run the command interactively to trust this version, or set "
                   f"{TRUST_EXTENSIONS_ENV}=1 to load extensions unprompted.", err=True)
        sys.exit(1)

    click.echo("Choose an option:")
    click.echo("  [y] Continue once")
    click.echo(f"  [t] Trust version {current_version}")
    click.echo("  [n] Cancel (default)")

    try:
        choice = click.prompt("Your choice", type=click.Choice(['y', 't', 'n']), default='n')
    except click.Abort:
        # Ctrl-C at the prompt means no, and must read as no to the caller.
        choice = 'n'

    if choice == 'n':
        click.echo("Extension loading cancelled.")
        sys.exit(1)
    elif choice == 't':
        add_trusted_extension(package_name, current_version)
        click.echo(f"✅ Trusted '{package_name}' v{current_version}")

def _read_dist_text(dist, name):
    """Read one metadata file, treating any failure as absence."""
    try:
        return dist.read_text(name)
    except (OSError, UnicodeDecodeError):
        return None

def _editable_source_root(dist):
    """The source tree an editable install points at, if it is one.

    A PEP 660 install records only its .pth shim in RECORD, so its real files
    appear nowhere else; direct_url.json is the only place that names them.
    It sits in the same metadata directory as everything else read here, so
    consulting it adds no surface that shipping the module would not.
    """
    raw = _read_dist_text(dist, 'direct_url.json')
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(info, dict):
        return None
    dir_info = info.get('dir_info')
    if not isinstance(dir_info, dict) or not dir_info.get('editable'):
        return None
    url = info.get('url') or ''
    if not url.startswith('file://'):
        return None
    try:
        return Path(unquote(urlparse(url).path)).resolve()
    except (OSError, ValueError):
        return None

def _module_origin(module_name):
    """Where importing `module_name` would actually take its code from.

    find_spec does not execute anything, and `module_name` is top level, so
    no parent package runs either -- the point is to look before loading.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError, AttributeError):
        return None
    if spec is None:
        return None

    location = spec.origin
    if location is None:
        # Namespace package: no __init__ to point at, but its search path is
        # still where the code would be found.
        locations = list(spec.submodule_search_locations or [])
        location = locations[0] if locations else None
    if not location:
        return None
    try:
        return Path(location).resolve()
    except (OSError, ValueError):
        return None

def _distribution_owns(dist, module_name, origin):
    """Whether `origin` is really part of `dist`.

    Every other check here describes the distribution's metadata, but the
    import resolves through sys.path and is under no obligation to land in
    that distribution's files. A bare directory carrying the right name and
    no metadata at all shadows an installed extension and inherits its
    verdict, [OFFICIAL] included.
    """
    for recorded in (dist.files or ()):
        try:
            if Path(dist.locate_file(recorded)).resolve() == origin:
                return True
        except (OSError, ValueError):
            continue

    root = _editable_source_root(dist)
    if root is None and not dist.files:
        # No RECORD to compare against; the installation root is all we have.
        try:
            root = Path(dist.locate_file('')).resolve()
        except (OSError, ValueError):
            return False
    if root is None:
        return False

    # Exactly where that root would place this module, and nowhere else:
    # "somewhere under the root" would accept any subdirectory of
    # site-packages, which is most of the shadowing it is meant to catch.
    return origin in (
        root / module_name / '__init__.py',   # package
        root / f'{module_name}.py',           # single-file module
        root / module_name,                   # namespace package
    )

def _describe_provenance(dist, origin):
    """Say where the code about to run actually comes from.

    A name and a version number are what the package asserts about itself.
    The path is the part a user can recognise, or fail to recognise.
    """
    lines = [f"   Code: {origin}"]

    installer = (_read_dist_text(dist, 'INSTALLER') or '').strip()
    if installer:
        lines.append(f"   Installed by: {installer}")

    raw = _read_dist_text(dist, 'direct_url.json')
    if raw:
        try:
            url = json.loads(raw).get('url')
        except (json.JSONDecodeError, AttributeError):
            url = None
        if url:
            editable = ' (editable)' if _editable_source_root(dist) else ''
            lines.append(f"   Installed from: {url}{editable}")
    return lines

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
            module_name = package_name.replace('-', '_')

            # Identity before anything else: every check below reasons about
            # `dist`, so they are worth nothing unless what gets imported is
            # actually this distribution's code.
            origin = _module_origin(module_name)
            if origin is None or not _distribution_owns(dist, module_name, origin):
                click.echo(
                    f"⚠️  Ignoring '{package_name}': '{module_name}' resolves to "
                    f"{origin or 'nothing importable'}, which is not part of "
                    "that distribution.", err=True)
                continue

            approved = (
                _trust_extensions
                or is_official_extension(package_name)
                or is_trusted_extension(package_name, current_version))

            # Version compatibility check
            if not check_version_compatibility(current_version, core_version):
                if approved:
                    warn_version_incompatibility(
                        package_name, current_version, core_version)
                else:
                    # Never approved by anyone, so it does not get to take the
                    # whole CLI down -- including the commands used to find it.
                    click.echo(
                        f"⚠️  Ignoring '{package_name}' v{current_version}: "
                        f"incompatible with halfORM v{core_version}.", err=True)
                continue

            # Security check for non-official extensions
            if not is_official_extension(package_name):
                warn_unofficial_extension(
                    package_name, current_version,
                    _describe_provenance(dist, origin))

            # Import extension
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
                    'display_name': display_name,
                    'pre_check': getattr(extension_module, 'pre_check', None),
                }

        except click.Abort:
            # A refusal is a decision, not a loading failure: it must reach the
            # caller instead of being downgraded to "extension unavailable".
            raise
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
@click.option('--untrust', metavar='EXTENSION', help="Remove extension from this project's trusted list")
@click.option('--trusted-extensions', is_flag=True, is_eager=True,
              callback=_set_trust_extensions,
              help=f'Skip security warnings (or set {TRUST_EXTENSIONS_ENV}=1)')
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
    # --trusted-extensions is recorded by its own eager callback, which runs
    # before --help can render the command list and load extensions.
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

def _ensure_extensions_registered():
    """Register extension commands on first use rather than at import.

    Registration prompts for consent, imports third-party code and can abort
    the process. Doing that while `half_orm.cli` is merely being imported made
    it a side effect of `import`, and -- worse -- put it before click had
    parsed the very options meant to govern it: `--trusted-extensions` could
    never skip a warning, and `--untrust` could not be reached without first
    clearing the prompt it exists to remove.
    """
    global _extensions_registered
    if _extensions_registered:
        return
    _extensions_registered = True
    register_extensions()

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

# Extensions are registered lazily, on the first command lookup: see
# _ensure_extensions_registered().

if __name__ == '__main__':
    main()