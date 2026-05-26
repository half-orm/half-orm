#!/usr/bin/env python3
"""
Tests for halfORM CLI functionality.

Tests cover:
- Extension discovery and registration
- Version compatibility checks
- Trust/untrust functionality
- CLI command integration
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

# Import the CLI module
import sys
sys.path.insert(0, '.')
from half_orm.cli import (
    main, discover_extensions, check_version_compatibility,
    is_trusted_extension, add_trusted_extension, remove_trusted_extension,
    load_cli_config, save_cli_config, get_config_file, OFFICIAL_EXTENSIONS
)


class TestVersionCompatibility:
    """Test version compatibility checking."""
    
    def test_compatible_versions(self):
        """Test compatible version combinations."""
        assert check_version_compatibility("1.2.3", "1.2.5") == True
        assert check_version_compatibility("1.2.0", "1.2.99") == True
        assert check_version_compatibility("2.0.1", "2.0.0") == True
    
    def test_incompatible_versions(self):
        """Test incompatible version combinations."""
        assert check_version_compatibility("1.2.3", "1.3.0") == False
        assert check_version_compatibility("1.2.3", "2.2.3") == False
        assert check_version_compatibility("2.0.0", "1.2.0") == False
    
    def test_malformed_versions(self):
        """Test handling of malformed version strings."""
        assert check_version_compatibility("invalid", "1.2.3") == False
        assert check_version_compatibility("1.2.3", "invalid") == False
        assert check_version_compatibility("1", "1.2.3") == False
        assert check_version_compatibility("1.2.3", "1") == False


class TestConfigManagement:
    """Test configuration file management."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = Path.cwd()
        
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_config_file_creation(self):
        """Test configuration file creation."""
        with patch('half_orm.cli.Path.cwd', return_value=Path(self.temp_dir)):
            config = {'test': 'value'}
            assert save_cli_config(config) == True
            
            config_file = Path(self.temp_dir) / '.half_orm_cli'
            assert config_file.exists()
            
            loaded = load_cli_config()
            assert loaded['test'] == 'value'
            assert 'last_updated' in loaded
    
    def test_trust_extension_management(self):
        """Test extension trust management."""
        with patch('half_orm.cli.Path.cwd', return_value=Path(self.temp_dir)):
            # Initially not trusted
            assert is_trusted_extension('test-ext', '1.0.0') == False
            
            # Add to trusted
            add_trusted_extension('test-ext', '1.0.0')
            assert is_trusted_extension('test-ext', '1.0.0') == True
            
            # Different version not trusted
            assert is_trusted_extension('test-ext', '1.0.1') == False
            
            # Remove from trusted
            assert remove_trusted_extension('test-ext') == True
            assert is_trusted_extension('test-ext', '1.0.0') == False
            
            # Remove non-existent
            assert remove_trusted_extension('non-existent') == False


class TestCLICommands:
    """Test CLI command functionality."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_help_command(self):
        """Test help command."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'halfORM' in result.output
        assert 'PostgreSQL-native ORM' in result.output
    
    def test_version_command(self):
        """Test version command."""
        # Use real version instead of patching to avoid CI issues
        import half_orm
        result = self.runner.invoke(main, ['version'])
        assert result.exit_code == 0
        assert half_orm.__version__ in result.output
    
    def test_list_extensions_no_extensions(self):
        """Test list extensions when none are installed."""
        with patch('half_orm.cli.discover_extensions', return_value={}):
            result = self.runner.invoke(main, ['--list-extensions'])
            assert result.exit_code == 0
            assert 'No extensions installed' in result.output
    
    def test_list_extensions_with_extensions(self):
        """Test list extensions with mock extensions."""
        mock_extensions = {
            'half-orm-inspect': {
                'package_name': 'half-orm-inspect',
                'version': '0.16.0',
                'display_name': 'inspect',
                'metadata': {
                    'description': 'Database inspection tools',
                    'commands': ['inspect']
                }
            }
        }
        
        with patch('half_orm.cli.discover_extensions', return_value=mock_extensions):
            with patch('half_orm.cli.is_official_extension', return_value=True):
                result = self.runner.invoke(main, ['--list-extensions'])
                assert result.exit_code == 0
                assert 'inspect' in result.output
                assert '0.16.0' in result.output
                assert '[OFFICIAL]' in result.output
    
    def test_untrust_extension(self):
        """Test untrusting an extension."""
        with patch('half_orm.cli.Path.cwd', return_value=Path(self.temp_dir)):
            # Add extension to trust first
            add_trusted_extension('half-orm-test', '0.16.0')
            
            # Untrust it
            result = self.runner.invoke(main, ['--untrust', 'test'])
            assert result.exit_code == 0
            assert 'Removed' in result.output
    
    def test_untrust_nonexistent_extension(self):
        """Test untrusting a non-existent extension."""
        with patch('half_orm.cli.Path.cwd', return_value=Path(self.temp_dir)):
            result = self.runner.invoke(main, ['--untrust', 'nonexistent'])
            assert result.exit_code == 0
            assert 'not in trusted list' in result.output


class TestExtensionDiscovery:
    """Test extension discovery functionality."""
    
    def test_extension_name_extraction(self):
        """Test extension name extraction from module names."""
        from half_orm.cli_utils import get_extension_name_from_module
        
        assert get_extension_name_from_module('half_orm_inspect.cli_extension') == 'inspect'
        assert get_extension_name_from_module('half_orm_dev.cli_extension') == 'dev'
        assert get_extension_name_from_module('half_orm_test_extension.cli_extension') == 'test-extension'
        assert get_extension_name_from_module('other_package.cli_extension') == 'other_package'
    
    @patch('half_orm.cli.distributions')
    @patch('half_orm.cli._cached_extensions', None)  # Clear cache
    def test_discover_extensions_with_mock(self, mock_distributions):
        """Test extension discovery with mocked distributions."""
        # Get real version to ensure compatibility
        import half_orm
        real_version = half_orm.__version__
        
        # Create mock distribution
        mock_dist = Mock()
        mock_dist.metadata = {'Name': 'half-orm-test-extension'}
        mock_dist.version = real_version  # Use compatible version
        mock_distributions.return_value = [mock_dist]
        
        # Mock the extension module
        mock_extension = Mock()
        mock_extension.__name__ = 'half_orm_test_extension.cli_extension'
        mock_extension.add_commands = Mock()
        mock_extension.EXTENSION_INFO = {
            'description': 'Test extension',
            'commands': ['test']
        }
        
        # Import importlib at module level to avoid issues
        import importlib
        original_import_module = importlib.import_module
        
        def mock_import_module(module_name):
            if module_name == 'half_orm_test_extension.cli_extension':
                return mock_extension
            else:
                # Let other imports work normally
                return original_import_module(module_name)
        
        with patch('importlib.import_module', side_effect=mock_import_module):
            with patch('half_orm.cli.is_official_extension', return_value=True):
                with patch('half_orm.cli._trust_extensions', True):
                    # Mock cli_utils functions
                    with patch('half_orm.cli_utils.get_extension_name_from_module', return_value='test-extension'):
                        with patch('half_orm.cli_utils.get_package_metadata', return_value={
                            'description': 'Test extension',
                            'commands': ['test']
                        }):
                            # Clear cached extensions
                            import half_orm.cli
                            half_orm.cli._cached_extensions = None
                            
                            extensions = discover_extensions()
                            assert 'half-orm-test-extension' in extensions
                            assert extensions['half-orm-test-extension']['version'] == real_version
                            assert extensions['half-orm-test-extension']['display_name'] == 'test-extension'

    @patch('half_orm.cli.distributions')
    def test_discover_extensions_version_incompatible(self, mock_distributions):
        """Test extension discovery with version incompatibility."""
        # Get real version and create an incompatible one
        import half_orm
        core_version = half_orm.__version__
        
        # Create incompatible version (different major.minor)
        # Use different variable names to avoid shadowing 'patch' function
        major_version, minor_version, patch_version = core_version.split('.')
        if int(minor_version) > 0:
            incompatible_version = f"{major_version}.{int(minor_version)-1}.0"
        else:
            # If minor is 0, change major_version
            incompatible_version = f"{max(0, int(major_version)-1)}.99.0"
        
        mock_dist = Mock()
        mock_dist.metadata = {'Name': 'half-orm-test-extension'}
        mock_dist.version = incompatible_version
        mock_distributions.return_value = [mock_dist]
        
        # Patch sys.exit to prevent the test from actually exiting
        with patch('half_orm.cli.sys.exit') as mock_exit:
            # Patch warn_version_incompatibility to verify it's called
            with patch('half_orm.cli.warn_version_incompatibility') as mock_warn:
                # Clear cached extensions
                import half_orm.cli
                half_orm.cli._cached_extensions = None
                
                # Call discover_extensions
                extensions = discover_extensions()
                
                # Verify that warn_version_incompatibility was called
                mock_warn.assert_called_once_with('half-orm-test-extension', incompatible_version, core_version)
                
                # The extension should not be in the returned extensions
                assert 'half-orm-test-extension' not in extensions

class TestSecurityWarnings:
    """Test security warning functionality."""
    
    def test_official_extension_no_warning(self):
        """Test that official extensions don't trigger warnings."""
        # Official extensions should skip ALL checks and not trigger any warnings
        with patch('half_orm.cli.click.echo') as mock_echo:
            with patch('half_orm.cli.click.prompt') as mock_prompt:
                # Mock the global state to ensure we test the right path
                with patch('half_orm.cli._trust_extensions', False):
                    with patch('half_orm.cli.is_official_extension', return_value=True):
                        from half_orm.cli import warn_unofficial_extension
                        warn_unofficial_extension('half-orm-inspect', '0.16.0')
                        # Should not show any warnings or prompts for official extensions
                        mock_echo.assert_not_called()
                        mock_prompt.assert_not_called()
    
    def test_trusted_extension_no_warning(self):
        """Test that trusted extensions don't trigger warnings."""
        with patch('half_orm.cli.click.echo') as mock_echo:
            with patch('half_orm.cli.click.prompt') as mock_prompt:
                with patch('half_orm.cli._trust_extensions', False):
                    with patch('half_orm.cli.is_official_extension', return_value=False):
                        with patch('half_orm.cli.is_trusted_extension', return_value=True):
                            from half_orm.cli import warn_unofficial_extension
                            warn_unofficial_extension('half-orm-test', '0.16.0')
                            # Should not show warnings or prompts for trusted extensions
                            mock_echo.assert_not_called()
                            mock_prompt.assert_not_called()
    
    def test_global_trust_no_warning(self):
        """Test that global trust mode skips warnings."""
        with patch('half_orm.cli.click.echo') as mock_echo:
            with patch('half_orm.cli.click.prompt') as mock_prompt:
                with patch('half_orm.cli._trust_extensions', True):
                    with patch('half_orm.cli.is_official_extension', return_value=False):
                        with patch('half_orm.cli.is_trusted_extension', return_value=False):
                            from half_orm.cli import warn_unofficial_extension
                            warn_unofficial_extension('half-orm-test', '0.16.0')
                            # Should not show warnings or prompts in global trust mode
                            mock_echo.assert_not_called()
                            mock_prompt.assert_not_called()
    
    def test_unofficial_extension_warning_cancel(self):
        """Test that unofficial extensions show warning and can be cancelled."""
        with patch('half_orm.cli.is_official_extension', return_value=False):
            with patch('half_orm.cli.is_trusted_extension', return_value=False):
                with patch('half_orm.cli._trust_extensions', False):
                    with patch('half_orm.cli.click.prompt', return_value='n') as mock_prompt:
                        with patch('half_orm.cli.sys.exit') as mock_exit:
                            from half_orm.cli import warn_unofficial_extension
                            warn_unofficial_extension('half-orm-test', '0.16.0')
                            mock_prompt.assert_called_once()
                            mock_exit.assert_called_once_with(1)
    
    def test_unofficial_extension_warning_trust(self):
        """Test that unofficial extensions can be trusted."""
        with patch('half_orm.cli.is_official_extension', return_value=False):
            with patch('half_orm.cli.is_trusted_extension', return_value=False):
                with patch('half_orm.cli._trust_extensions', False):
                    with patch('half_orm.cli.click.prompt', return_value='t') as mock_prompt:
                        with patch('half_orm.cli.add_trusted_extension') as mock_trust:
                            from half_orm.cli import warn_unofficial_extension
                            warn_unofficial_extension('half-orm-test', '0.16.0')
                            mock_prompt.assert_called_once()
                            mock_trust.assert_called_once_with('half-orm-test', '0.16.0')


class TestPreCheck:
    """Test pre_check hook in the extension mechanism."""

    def setup_method(self):
        self.runner = CliRunner()

    def _make_extensions(self, pre_check=None):
        """Build a minimal mock extensions dict."""
        return {
            'half-orm-dummy': {
                'module': Mock(),
                'package_name': 'half-orm-dummy',
                'version': '0.0.0',
                'metadata': {'description': ''},
                'display_name': 'dummy',
                'pre_check': pre_check,
            }
        }

    def test_pre_check_stored_when_defined(self):
        """pre_check attribute is captured during discovery."""
        import half_orm
        real_version = half_orm.__version__

        mock_ext = Mock()
        mock_ext.__name__ = 'half_orm_dummy.cli_extension'
        mock_ext.add_commands = Mock()

        def pre_check_fn(ctx):
            pass

        mock_ext.pre_check = pre_check_fn

        mock_dist = Mock()
        mock_dist.metadata = {'Name': 'half-orm-dummy'}
        mock_dist.version = real_version

        import importlib
        original = importlib.import_module

        def fake_import(name):
            if name == 'half_orm_dummy.cli_extension':
                return mock_ext
            return original(name)

        import half_orm.cli
        half_orm.cli._cached_extensions = None

        with patch('half_orm.cli.distributions', return_value=[mock_dist]):
            with patch('importlib.import_module', side_effect=fake_import):
                with patch('half_orm.cli.is_official_extension', return_value=True):
                    with patch('half_orm.cli_utils.get_extension_name_from_module', return_value='dummy'):
                        with patch('half_orm.cli_utils.get_package_metadata', return_value={'description': ''}):
                            exts = discover_extensions()

        assert 'half-orm-dummy' in exts
        assert exts['half-orm-dummy']['pre_check'] is pre_check_fn

        half_orm.cli._cached_extensions = None

    def test_pre_check_absent_when_not_defined(self):
        """pre_check is None when the extension does not define it."""
        import half_orm
        real_version = half_orm.__version__

        mock_ext = Mock(spec=['__name__', 'add_commands'])
        mock_ext.__name__ = 'half_orm_dummy.cli_extension'
        mock_ext.add_commands = Mock()

        mock_dist = Mock()
        mock_dist.metadata = {'Name': 'half-orm-dummy'}
        mock_dist.version = real_version

        import importlib
        original = importlib.import_module

        def fake_import(name):
            if name == 'half_orm_dummy.cli_extension':
                return mock_ext
            return original(name)

        import half_orm.cli
        half_orm.cli._cached_extensions = None

        with patch('half_orm.cli.distributions', return_value=[mock_dist]):
            with patch('importlib.import_module', side_effect=fake_import):
                with patch('half_orm.cli.is_official_extension', return_value=True):
                    with patch('half_orm.cli_utils.get_extension_name_from_module', return_value='dummy'):
                        with patch('half_orm.cli_utils.get_package_metadata', return_value={'description': ''}):
                            exts = discover_extensions()

        assert 'half-orm-dummy' in exts
        assert exts['half-orm-dummy']['pre_check'] is None

        half_orm.cli._cached_extensions = None

    def test_pre_check_called_before_command_resolution(self):
        """pre_check is invoked when a command is resolved."""
        called = []

        def pre_check_fn(ctx):
            called.append(True)

        exts = self._make_extensions(pre_check=pre_check_fn)

        with patch('half_orm.cli.discover_extensions', return_value=exts):
            result = self.runner.invoke(main, ['version'])

        assert called, "pre_check was not called"
        assert result.exit_code == 0

    def test_pre_check_click_exception_aborts(self):
        """A ClickException raised in pre_check aborts command execution."""
        import click

        def pre_check_fn(ctx):
            raise click.ClickException("pre_check failed")

        exts = self._make_extensions(pre_check=pre_check_fn)

        with patch('half_orm.cli.discover_extensions', return_value=exts):
            result = self.runner.invoke(main, ['version'])

        assert result.exit_code != 0
        assert 'pre_check failed' in result.output

    def test_pre_check_generic_exception_wrapped(self):
        """A non-Click exception raised in pre_check is wrapped in ClickException."""
        def pre_check_fn(ctx):
            raise RuntimeError("something went wrong")

        exts = self._make_extensions(pre_check=pre_check_fn)

        with patch('half_orm.cli.discover_extensions', return_value=exts):
            result = self.runner.invoke(main, ['version'])

        assert result.exit_code != 0
        assert 'something went wrong' in result.output

    def test_no_pre_check_does_not_break(self):
        """Extensions without pre_check are unaffected by the new mechanism."""
        exts = self._make_extensions(pre_check=None)
        # Register a real dummy command so the CLI has something to resolve
        import click as _click

        @_click.command(name='dummy-cmd')
        def _dummy():
            _click.echo('ok')

        with patch('half_orm.cli.discover_extensions', return_value=exts):
            with patch.object(main, 'get_command', return_value=_dummy):
                result = self.runner.invoke(main, ['dummy-cmd'])

        assert result.exit_code == 0


class TestIntegrationTests:
    """Integration tests for complete CLI workflows."""
    
    def setup_method(self):
        """Set up integration test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_extension_workflow(self):
        """Test complete extension trust/untrust workflow."""
        with patch('half_orm.cli.Path.cwd', return_value=Path(self.temp_dir)):
            # Mock extension discovery
            mock_extensions = {
                'half-orm-test': {
                    'package_name': 'half-orm-test',
                    'version': '0.16.0',
                    'display_name': 'test',
                    'metadata': {'description': 'Test extension'}
                }
            }
            
            with patch('half_orm.cli.discover_extensions', return_value=mock_extensions):
                with patch('half_orm.cli.is_official_extension', return_value=False):
                    # List extensions
                    result = self.runner.invoke(main, ['--list-extensions'])
                    assert result.exit_code == 0
                    assert '[UNOFFICIAL]' in result.output
                    
                    # Trust extension (simulate user interaction)
                    add_trusted_extension('half-orm-test', '0.16.0')
                    
                    # List again - should show as trusted
                    with patch('half_orm.cli.is_trusted_extension', return_value=True):
                        result = self.runner.invoke(main, ['--list-extensions'])
                        assert result.exit_code == 0
                        assert '[TRUSTED]' in result.output
                    
                    # Untrust extension
                    result = self.runner.invoke(main, ['--untrust', 'half-orm-test'])
                    assert result.exit_code == 0
                    assert 'Removed' in result.output


if __name__ == '__main__':
    # Run specific test categories
    import sys
    
    if len(sys.argv) > 1:
        test_class = sys.argv[1]
        pytest.main([f'-v', f'test_cli.py::{test_class}'])
    else:
        # Run all tests
        pytest.main(['-v', 'test_cli.py'])