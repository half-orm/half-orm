"""
halfORM CLI utilities for extensions

Provides common functionality that extensions can use to integrate 
with the halfORM CLI system.
"""

from typing import Optional
from importlib.metadata import metadata, PackageNotFoundError
import click


def get_extension_name_from_module(module_name: str) -> str:
    """
    Extract extension name from module name.

    Args:
        module_name: The __name__ of the extension module

    Returns:
        The clean extension name (e.g., 'inspect', 'test-extension')

    Examples:
        'half_orm_inspect.cli_extension' -> 'inspect'
        'half_orm_test_extension.cli_extension' -> 'test-extension'
    """
    # Extract the main package name from module hierarchy
    if '.' in module_name:
        package_name = module_name.split('.')[0]
    else:
        package_name = module_name

    # Convert underscores back to hyphens and remove half_orm prefix
    if package_name.startswith('half_orm_'):
        clean_name = package_name.replace('half_orm_', '')
        # Convert underscores to hyphens for multi-word extensions
        return clean_name.replace('_', '-')

    return package_name


def get_package_metadata(module):
    """
    Extract package metadata from module.

    Args:
        module: The extension module

    Returns:
        dict: Package metadata (version, author, description, etc.)
    """
    # Convert module name to package name
    module_name = module.__name__
    if '.' in module_name:
        package_name = module_name.split('.')[0]
    else:
        package_name = module_name

    # Convert underscores back to hyphens for package lookup
    package_name = package_name.replace('_', '-')

    try:
        pkg_metadata = metadata(package_name)
    except PackageNotFoundError:
        return {
            'version': 'unknown',
            'author': 'unknown',
            'description': '',
            'package_name': package_name
        }

    return {
        'version': pkg_metadata.get('Version', 'unknown'),
        'author': pkg_metadata.get('Author', 'unknown'),
        'description': pkg_metadata.get('Summary', pkg_metadata.get('Description', '')),
        'package_name': package_name
    }


def get_extension_commands(extension_group):
    """
    Auto-discover commands from a Click group.

    Args:
        extension_group: Click group object

    Returns:
        list: List of command names
    """
    return list(extension_group.commands.keys())


def create_and_register_extension(main_group, module, description: Optional[str] = None):
    """
    Create and register an extension group as a decorator.

    Args:
        main_group: The main halfORM CLI group
        module: The extension module (use sys.modules[__name__])
        description: Optional description override. If None, uses module docstring or package description

    Example:
        import sys

        @create_and_register_extension(main_group, sys.modules[__name__])
        def my_extension_commands():
            '''Extension description from docstring'''
            pass

        @my_extension_commands.command()
        def some_command():
            pass
    """
    # Extract extension name from the module
    extension_name = get_extension_name_from_module(module.__name__)

    def decorator(func):
        # Use description parameter, or function docstring, or package description
        if description is None:
            # Try function docstring first
            func_description = func.__doc__.strip() if func.__doc__ else ''
            if not func_description:
                # Fallback to package description
                metadata = get_package_metadata(module)
                func_description = metadata.get('description', '')
        else:
            func_description = description

        # Create the Click group
        extension_group = click.group(name=extension_name, help=func_description)(func)
        # Register it with the main group
        main_group.add_command(extension_group)
        # Return the group so commands can be added to it
        return extension_group

    return decorator


def add_direct_command(main_group, module, command_name: Optional[str] = None, description: Optional[str] = None):
    """
    Add a command directly to the main CLI group without creating a subgroup.

    This is useful when you want a simple interface like:
        half_orm inspect database
    Instead of:
        half_orm inspect inspect database

    Args:
        main_group: The main halfORM CLI group
        module: The extension module (use sys.modules[__name__])
        command_name: Name of the command. If None, uses extension name from module
        description: Command description. If None, uses module docstring or package description

    Returns:
        A decorator function for the command implementation

    Example:
        import sys

        @add_direct_command(main_group, sys.modules[__name__])
        @click.argument('target')
        @click.option('--json', is_flag=True)
        def my_command(target, json):
            '''Command description from docstring'''
            # Command implementation
            pass
    """
    # Determine command name
    if command_name is None:
        command_name = get_extension_name_from_module(module.__name__)

    def decorator(func):
        # Use description parameter, or function docstring, or package description
        if description is None:
            # Try function docstring first
            func_description = func.__doc__.strip() if func.__doc__ else ''
            if not func_description:
                # Fallback to package description
                metadata = get_package_metadata(module)
                func_description = metadata.get('description', '')
        else:
            func_description = description

        # Create the Click command directly
        command = click.command(name=command_name, help=func_description)(func)
        # Register it with the main group
        main_group.add_command(command)
        # Return the command
        return command

    return decorator


def create_extension(main_group, module, use_group: bool = True, 
                          command_name: Optional[str] = None, 
                          description: Optional[str] = None):
    """
    Extension creator that can create either a group or direct command.

    Args:
        main_group: The main halfORM CLI group
        module: The extension module (use sys.modules[__name__])
        use_group: If True (default), creates a group. If False, creates a direct command
        command_name: Name override (for both group and command)
        description: Description override

    Returns:
        Decorator function

    Example:
        import sys

        # Creates direct command: half_orm inspect
        @create_smart_extension(main_group, sys.modules[__name__], use_group=False)
        @click.argument('target')
        def inspect_command(target):
            pass

        # Creates group: half_orm dev <subcommand>
        @create_smart_extension(main_group, sys.modules[__name__], use_group=True)
        def dev_commands():
            pass
    """
    if use_group:
        return create_and_register_extension(main_group, module, description)
    else:
        return add_direct_command(main_group, module, command_name, description)