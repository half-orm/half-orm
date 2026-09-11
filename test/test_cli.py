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
import contextlib
import json
import os
import stat
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

# Import the CLI module
import sys
sys.path.insert(0, '.')
import half_orm
from half_orm import cli as half_orm_cli
from half_orm.cli import (
    main, discover_extensions, check_version_compatibility,
    is_trusted_extension, is_official_extension, add_trusted_extension,
    remove_trusted_extension, load_cli_config, save_cli_config,
    get_config_file, get_project_key, LEGACY_CONFIG_NAME, OFFICIAL_EXTENSIONS
)


@contextlib.contextmanager
def identity_checks_satisfied():
    """Let a fabricated distribution pass the module-ownership check.

    Tests that mock `distributions` have no files on disk, so the real check
    -- is the importable module actually part of this distribution? -- has
    nothing to look at and rightly refuses.
    """
    with patch('half_orm.cli._module_origin',
               return_value=Path('/fake/site-packages/mod/__init__.py')), \
            patch('half_orm.cli._distribution_owns', return_value=True):
        yield


@pytest.fixture(autouse=True)
def isolated_cli_config(tmp_path, monkeypatch):
    """Keep every test out of the developer's own trust store.

    get_config_file() deliberately resolves under the user's home, so without
    this the suite would read -- and write -- the real configuration.
    """
    monkeypatch.setenv('HALF_ORM_CLI_CONFIG', str(tmp_path / 'cli.json'))
    monkeypatch.delenv('HALF_ORM_TRUST_EXTENSIONS', raising=False)
    monkeypatch.setattr(half_orm_cli, '_legacy_config_warned', False)
    monkeypatch.setattr(half_orm_cli, '_extensions_registered', False)
    monkeypatch.setattr(half_orm_cli, '_cached_extensions', None)


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

            assert get_config_file().exists()

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

    @pytest.fixture(autouse=True)
    def _fabricated_distributions_own_their_modules(self):
        with identity_checks_satisfied():
            yield
    
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
        
        # An incompatible version is a hard failure only for an extension the
        # user actually relies on; see the unapproved case below.
        with patch('half_orm.cli.is_official_extension', return_value=True), \
                patch('half_orm.cli.sys.exit') as mock_exit:
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

    @patch('half_orm.cli.distributions')
    def test_unapproved_incompatible_extension_does_not_halt(self, mock_distributions):
        """An extension nobody approved must not take the whole CLI down.

        The version check used to run first and exit(1), so any installed
        half-orm-* package could brick every command -- including the ones
        used to diagnose and remove it.
        """
        import half_orm
        major, minor, _ = half_orm.__version__.split('.')
        incompatible = f"{major}.{int(minor) + 1}.0"

        mock_dist = Mock()
        mock_dist.metadata = {'Name': 'half-orm-stranger'}
        mock_dist.version = incompatible
        mock_distributions.return_value = [mock_dist]

        with patch('half_orm.cli.sys.exit') as mock_exit, \
                patch('half_orm.cli.warn_unofficial_extension') as mock_prompt:
            half_orm_cli._cached_extensions = None
            extensions = discover_extensions()

        assert 'half-orm-stranger' not in extensions
        mock_exit.assert_not_called()
        # ...and it is refused before anyone is asked to consent to it.
        mock_prompt.assert_not_called()


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
        with patch('half_orm.cli._stdin_is_interactive', return_value=True), \
                patch('half_orm.cli.is_official_extension', return_value=False):
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
        with patch('half_orm.cli._stdin_is_interactive', return_value=True), \
                patch('half_orm.cli.is_official_extension', return_value=False):
            with patch('half_orm.cli.is_trusted_extension', return_value=False):
                with patch('half_orm.cli._trust_extensions', False):
                    with patch('half_orm.cli.click.prompt', return_value='t') as mock_prompt:
                        with patch('half_orm.cli.add_trusted_extension') as mock_trust:
                            from half_orm.cli import warn_unofficial_extension
                            warn_unofficial_extension('half-orm-test', '0.16.0')
                            mock_prompt.assert_called_once()
                            mock_trust.assert_called_once_with('half-orm-test', '0.16.0')


class TestTrustStoreLocation:
    """The trust store must not be writable by the code it is protecting.

    It suppresses the consent prompt for unofficial extensions, so a checkout
    able to write its own entries would grant itself silent consent -- and a
    `git clone` produces files owned by the victim, which is why no permission
    check can substitute for keeping the store out of the project.
    """

    def test_store_lives_outside_any_project(self, monkeypatch, tmp_path):
        """The default location is under the user's profile, not the CWD."""
        monkeypatch.delenv('HALF_ORM_CLI_CONFIG', raising=False)
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        monkeypatch.chdir(tmp_path)

        config_file = get_config_file()
        assert config_file.name == 'cli.json'
        assert config_file.parent.name == 'half_orm'
        assert Path.home() in config_file.parents
        assert tmp_path not in config_file.parents

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='Windows uses %APPDATA%, not XDG')
    def test_xdg_config_home_is_honoured(self, monkeypatch, tmp_path):
        monkeypatch.delenv('HALF_ORM_CLI_CONFIG', raising=False)
        monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
        assert get_config_file() == tmp_path / 'half_orm' / 'cli.json'

    @pytest.mark.skipif(sys.platform != 'win32', reason='Windows-only layout')
    def test_appdata_is_honoured(self, monkeypatch, tmp_path):
        monkeypatch.delenv('HALF_ORM_CLI_CONFIG', raising=False)
        monkeypatch.setenv('APPDATA', str(tmp_path))
        assert get_config_file() == tmp_path / 'half_orm' / 'cli.json'

    def test_explicit_override_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))
        monkeypatch.setenv('HALF_ORM_CLI_CONFIG', str(tmp_path / 'chosen.json'))
        assert get_config_file() == tmp_path / 'chosen.json'

    def test_project_local_store_grants_nothing(self, monkeypatch, tmp_path):
        """A .half_orm_cli shipped in a repository must not be honoured."""
        project = tmp_path / 'hostile'
        project.mkdir()
        (project / LEGACY_CONFIG_NAME).write_text(json.dumps({
            'trusted_extensions': {
                'half-orm-evil': {'version': '1.0.0'}
            }
        }))
        monkeypatch.chdir(project)

        assert is_trusted_extension('half-orm-evil', '1.0.0') is False

    def test_project_local_store_is_reported_not_ignored_silently(
            self, monkeypatch, tmp_path, capsys):
        """Silently dropping the old file would look like a bug to its owner."""
        project = tmp_path / 'legacy'
        project.mkdir()
        (project / LEGACY_CONFIG_NAME).write_text('{}')
        monkeypatch.chdir(project)

        load_cli_config()
        first = capsys.readouterr().err
        assert LEGACY_CONFIG_NAME in first

        # ...but only once, so it cannot drown the security prompt itself.
        load_cli_config()
        assert capsys.readouterr().err == ''

    def test_trust_does_not_leak_to_another_project(self, monkeypatch, tmp_path):
        one = tmp_path / 'one'
        two = tmp_path / 'two'
        for path in (one, two):
            (path / '.git').mkdir(parents=True)

        monkeypatch.chdir(one)
        add_trusted_extension('half-orm-ext', '1.0.0')
        assert is_trusted_extension('half-orm-ext', '1.0.0') is True

        monkeypatch.chdir(two)
        assert is_trusted_extension('half-orm-ext', '1.0.0') is False

    def test_trust_is_reused_from_a_subdirectory(self, monkeypatch, tmp_path):
        """Re-prompting inside the same project trains users to answer blind."""
        project = tmp_path / 'proj'
        (project / '.git').mkdir(parents=True)
        deep = project / 'a' / 'b'
        deep.mkdir(parents=True)

        monkeypatch.chdir(project)
        add_trusted_extension('half-orm-ext', '1.0.0')

        monkeypatch.chdir(deep)
        assert get_project_key() == str(project.resolve())
        assert is_trusted_extension('half-orm-ext', '1.0.0') is True

    def test_untrust_only_clears_the_current_project(self, monkeypatch, tmp_path):
        one = tmp_path / 'one'
        two = tmp_path / 'two'
        for path in (one, two):
            (path / '.git').mkdir(parents=True)

        for path in (one, two):
            monkeypatch.chdir(path)
            add_trusted_extension('half-orm-ext', '1.0.0')

        monkeypatch.chdir(one)
        assert remove_trusted_extension('half-orm-ext') is True
        assert is_trusted_extension('half-orm-ext', '1.0.0') is False

        monkeypatch.chdir(two)
        assert is_trusted_extension('half-orm-ext', '1.0.0') is True

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='POSIX permission bits; Windows relies on the '
                               'profile ACL of %APPDATA%')
    def test_store_is_written_owner_only(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        add_trusted_extension('half-orm-ext', '1.0.0')

        config_file = get_config_file()
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(config_file.parent.stat().st_mode) == 0o700

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='os.chmod only toggles the read-only flag there')
    def test_widened_permissions_are_narrowed_again(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        add_trusted_extension('half-orm-ext', '1.0.0')
        config_file = get_config_file()

        os.chmod(config_file, 0o644)
        add_trusted_extension('half-orm-other', '1.0.0')
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600

    @pytest.mark.parametrize('content', [
        'not json at all {{{',
        '[1, 2, 3]',
        '{"trusted_extensions": "everything"}',
        '{"trusted_extensions": {"__project__": "everything"}}',
        '{"trusted_extensions": {"__project__": {"half-orm-ext": "yes"}}}',
    ])
    def test_malformed_store_grants_nothing(self, monkeypatch, tmp_path, content):
        """Every shape a broken store can take must read as "not trusted"."""
        monkeypatch.chdir(tmp_path)
        content = content.replace('__project__', get_project_key())
        get_config_file().parent.mkdir(parents=True, exist_ok=True)
        get_config_file().write_text(content)

        assert is_trusted_extension('half-orm-ext', '1.0.0') is False


def _write_shadow_module(tmp_path, module='half_orm_probe'):
    """A bare directory of the right name, carrying no metadata whatsoever.

    This is the whole attack: nothing here claims to be an extension, yet it
    is what `import` finds first.
    """
    root = tmp_path / 'shadow'
    package = root / module
    package.mkdir(parents=True)
    marker = tmp_path / 'shadow-was-imported'
    (package / '__init__.py').write_text('')
    (package / 'cli_extension.py').write_text(
        'import pathlib\n'
        f'pathlib.Path({str(marker)!r}).write_text("imported")\n'
        'def add_commands(group):\n'
        '    pass\n')
    return root, marker


def _write_probe_extension(tmp_path):
    """Install a discoverable extension that records the fact it was imported.

    A real .dist-info on sys.path is the only faithful way to test what
    `import half_orm.cli` does: mocking `distributions` would test the mock.
    """
    marker = tmp_path / 'probe-was-imported'
    package = tmp_path / 'half_orm_probe'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'cli_extension.py').write_text(
        'import pathlib\n'
        f'pathlib.Path({str(marker)!r}).write_text("imported")\n'
        'def add_commands(group):\n'
        '    pass\n')

    dist_info = tmp_path / f'half_orm_probe-{half_orm.__version__}.dist-info'
    dist_info.mkdir()
    (dist_info / 'METADATA').write_text(
        'Metadata-Version: 2.1\n'
        'Name: half-orm-probe\n'
        f'Version: {half_orm.__version__}\n')
    (dist_info / 'WHEEL').write_text('Wheel-Version: 1.0\n')
    return marker


def _run_in_subprocess(code, tmp_path, env_extra=None, extra_paths=None):
    """Run `code` in a fresh interpreter that can discover the probe."""
    repo_root = Path(half_orm.__file__).resolve().parent.parent
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(
        [str(path) for path in (extra_paths or ())] + [str(repo_root), str(tmp_path)])
    env['HALF_ORM_CLI_CONFIG'] = str(tmp_path / 'cli.json')
    env.pop('HALF_ORM_TRUST_EXTENSIONS', None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, '-c', code], env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=120)


class TestRegistrationTiming:
    """Extension loading must not outrun the options that govern it.

    It used to run at module import: before click had parsed argv, and as a
    side effect of `import half_orm.cli` in any program at all.
    """

    def test_import_loads_no_extension(self, tmp_path):
        """Importing the module must not execute third-party code."""
        marker = _write_probe_extension(tmp_path)

        result = _run_in_subprocess('import half_orm.cli', tmp_path)

        assert result.returncode == 0, result.stderr
        assert not marker.exists()
        assert result.stderr == ''

    def test_import_asks_nothing_and_exits_nothing(self, tmp_path):
        """A consent prompt on stdin must never be an import side effect."""
        _write_probe_extension(tmp_path)

        result = _run_in_subprocess(
            'import half_orm.cli\nprint("still running")', tmp_path)

        assert result.returncode == 0, result.stderr
        assert 'still running' in result.stdout

    def test_trusted_extensions_flag_actually_skips_the_warning(self, tmp_path):
        """The flag was parsed after registration, so it could skip nothing."""
        marker = _write_probe_extension(tmp_path)
        code = ("import sys\n"
                "sys.argv = ['half_orm', '--trusted-extensions', '--list-extensions']\n"
                "from half_orm.cli import main\n"
                "main()\n")

        result = _run_in_subprocess(code, tmp_path)

        assert result.returncode == 0, result.stderr
        assert marker.exists()
        assert 'WARNING' not in result.stderr

    def test_environment_variable_skips_the_warning(self, tmp_path):
        """CI has no terminal, so the escape hatch cannot be a prompt."""
        marker = _write_probe_extension(tmp_path)
        code = ("import sys\n"
                "sys.argv = ['half_orm', '--list-extensions']\n"
                "from half_orm.cli import main\n"
                "main()\n")

        result = _run_in_subprocess(
            code, tmp_path, {'HALF_ORM_TRUST_EXTENSIONS': '1'})

        assert result.returncode == 0, result.stderr
        assert marker.exists()

    def test_unattended_run_refuses_loudly(self, tmp_path):
        """Without a terminal the extension is refused, not silently dropped."""
        marker = _write_probe_extension(tmp_path)
        code = ("import sys\n"
                "sys.argv = ['half_orm', '--list-extensions']\n"
                "from half_orm.cli import main\n"
                "main()\n")

        result = _run_in_subprocess(code, tmp_path)

        assert result.returncode == 1
        assert not marker.exists()
        assert 'Refusing to load it' in result.stderr

    def test_untrust_needs_no_extension_loading(self):
        """Clearing trust must not require clearing the prompt first."""
        runner = CliRunner()
        with patch('half_orm.cli.register_extensions') as mock_register:
            result = runner.invoke(main, ['--untrust', 'probe'])

        assert result.exit_code == 0
        mock_register.assert_not_called()

    def test_registration_happens_once(self):
        with patch('half_orm.cli.register_extensions') as mock_register:
            half_orm_cli._ensure_extensions_registered()
            half_orm_cli._ensure_extensions_registered()

        mock_register.assert_called_once()


class TestModuleIdentity:
    """What is checked and what is imported must be the same thing.

    Every verdict -- [OFFICIAL], trusted, version-compatible -- is reached by
    reading a distribution's metadata, while `importlib` resolves the module
    through sys.path and is free to land somewhere else entirely.
    """

    LIST_EXTENSIONS = ("import sys\n"
                       "sys.argv = ['half_orm', '--list-extensions']\n"
                       "from half_orm.cli import main\n"
                       "main()\n")

    def test_shadowing_directory_is_refused(self, tmp_path):
        """A metadata-less directory must not inherit a distribution's verdict."""
        probe_marker = _write_probe_extension(tmp_path)
        shadow_root, shadow_marker = _write_shadow_module(tmp_path)

        result = _run_in_subprocess(
            self.LIST_EXTENSIONS, tmp_path,
            {'HALF_ORM_TRUST_EXTENSIONS': '1'},
            extra_paths=[shadow_root])

        assert not shadow_marker.exists(), 'the shadowing module was executed'
        assert not probe_marker.exists(), 'the distribution was loaded anyway'
        assert 'is not part of that distribution' in result.stderr

    def test_genuine_distribution_is_accepted(self, tmp_path):
        """The check must not reject a plainly correct installation."""
        probe_marker = _write_probe_extension(tmp_path)

        result = _run_in_subprocess(
            self.LIST_EXTENSIONS, tmp_path, {'HALF_ORM_TRUST_EXTENSIONS': '1'})

        assert result.returncode == 0, result.stderr
        assert probe_marker.exists()

    def test_recorded_file_is_owned(self, tmp_path):
        """A file listed in RECORD belongs to the distribution."""
        origin = tmp_path / 'site' / 'half_orm_x' / '__init__.py'
        origin.parent.mkdir(parents=True)
        origin.write_text('')

        dist = Mock()
        dist.files = [Path('half_orm_x/__init__.py')]
        dist.locate_file = lambda name: tmp_path / 'site' / str(name)
        dist.read_text = Mock(return_value=None)

        assert half_orm_cli._distribution_owns(dist, 'half_orm_x', origin.resolve()) is True

    def test_editable_install_is_owned(self, tmp_path):
        """PEP 660 records only its .pth shim, never the source files.

        Rejecting editable installs would break the way extensions are
        developed, so direct_url.json has to be consulted.
        """
        source = tmp_path / 'src'
        origin = source / 'half_orm_x' / '__init__.py'
        origin.parent.mkdir(parents=True)
        origin.write_text('')
        site = tmp_path / 'site'
        site.mkdir()

        direct_url = json.dumps(
            {'dir_info': {'editable': True}, 'url': source.resolve().as_uri()})
        dist = Mock()
        dist.files = [Path('__editable__.half_orm_x.pth')]
        dist.locate_file = lambda name: site / str(name)
        dist.read_text = lambda name: (
            direct_url if name == 'direct_url.json' else None)

        assert half_orm_cli._distribution_owns(dist, 'half_orm_x', origin.resolve()) is True

    def test_non_editable_direct_url_grants_nothing(self, tmp_path):
        """Only the editable case needs the exemption, so only it gets it."""
        outside = tmp_path / 'elsewhere' / 'half_orm_x' / '__init__.py'
        outside.parent.mkdir(parents=True)
        outside.write_text('')
        site = tmp_path / 'site'
        site.mkdir()

        direct_url = json.dumps(
            {'dir_info': {}, 'url': (tmp_path / 'elsewhere').resolve().as_uri()})
        dist = Mock()
        dist.files = [Path('half_orm_x/__init__.py')]
        dist.locate_file = lambda name: site / str(name)
        dist.read_text = lambda name: (
            direct_url if name == 'direct_url.json' else None)

        assert half_orm_cli._distribution_owns(dist, 'half_orm_x', outside.resolve()) is False

    def test_vcs_install_gets_no_exemption(self, tmp_path):
        """`pip install git+URL` copies its files in, so RECORD covers it.

        Its direct_url.json carries vcs_info and no dir_info, and must not be
        read as an editable install: the exemption exists only because PEP 660
        keeps its sources outside RECORD.
        """
        site = tmp_path / 'site'
        site.mkdir()
        dist = Mock()
        dist.files = []
        dist.locate_file = lambda name: site / str(name)
        dist.read_text = lambda name: (
            json.dumps({'url': 'file:///home/joel/devel/half-orm',
                        'vcs_info': {'vcs': 'git', 'commit_id': '8e991c0'}})
            if name == 'direct_url.json' else None)

        assert half_orm_cli._editable_source_root(dist) is None

    def test_module_origin_does_not_import(self, tmp_path, monkeypatch):
        """Looking must not be loading: find_spec runs no module code."""
        package = tmp_path / 'half_orm_boom'
        package.mkdir()
        (package / '__init__.py').write_text('raise RuntimeError("imported!")\n')
        monkeypatch.syspath_prepend(str(tmp_path))

        origin = half_orm_cli._module_origin('half_orm_boom')

        assert origin == (package / '__init__.py').resolve()


class TestProvenanceInPrompt:
    """Consent to a name and a version number is consent to nothing checkable."""

    def _dist(self, installer=None, direct_url=None):
        dist = Mock()
        dist.read_text = lambda name: {
            'INSTALLER': installer, 'direct_url.json': direct_url}.get(name)
        return dist

    def test_prompt_names_the_file_that_will_run(self, capsys):
        origin = Path('/opt/somewhere/half_orm_x/__init__.py')
        lines = half_orm_cli._describe_provenance(self._dist(), origin)

        assert any(str(origin) in line for line in lines)

    def test_prompt_reports_the_installer(self):
        lines = half_orm_cli._describe_provenance(
            self._dist(installer='pip\n'), Path('/x'))

        assert any('pip' in line for line in lines)

    def test_prompt_flags_an_editable_install(self):
        direct_url = json.dumps(
            {'dir_info': {'editable': True}, 'url': 'file:///home/dev/x'})
        lines = half_orm_cli._describe_provenance(
            self._dist(direct_url=direct_url), Path('/x'))

        assert any('editable' in line for line in lines)

    def test_provenance_reaches_the_warning(self, capsys):
        with patch('half_orm.cli._stdin_is_interactive', return_value=False), \
                patch('half_orm.cli.is_official_extension', return_value=False), \
                patch('half_orm.cli.is_trusted_extension', return_value=False), \
                patch('half_orm.cli._trust_extensions', False):
            with pytest.raises(SystemExit):
                half_orm_cli.warn_unofficial_extension(
                    'half-orm-x', '1.0.0', ['   Code: /opt/x/__init__.py'])

        assert '/opt/x/__init__.py' in capsys.readouterr().err


class TestUnattendedConsent:
    """What happens when there is nobody to answer the prompt."""

    def test_refusal_is_an_error_not_a_silent_skip(self):
        with patch('half_orm.cli._stdin_is_interactive', return_value=False), \
                patch('half_orm.cli.is_official_extension', return_value=False), \
                patch('half_orm.cli.is_trusted_extension', return_value=False), \
                patch('half_orm.cli._trust_extensions', False), \
                patch('half_orm.cli.click.prompt') as mock_prompt:
            with pytest.raises(SystemExit) as exc:
                half_orm_cli.warn_unofficial_extension('half-orm-x', '1.0.0')

        assert exc.value.code == 1
        mock_prompt.assert_not_called()

    def test_ctrl_c_at_the_prompt_reads_as_no(self):
        """click.Abort is a RuntimeError, and used to be swallowed upstream."""
        with patch('half_orm.cli._stdin_is_interactive', return_value=True), \
                patch('half_orm.cli.is_official_extension', return_value=False), \
                patch('half_orm.cli.is_trusted_extension', return_value=False), \
                patch('half_orm.cli._trust_extensions', False), \
                patch('half_orm.cli.click.prompt', side_effect=__import__('click').Abort), \
                patch('half_orm.cli.add_trusted_extension') as mock_trust:
            with pytest.raises(SystemExit) as exc:
                half_orm_cli.warn_unofficial_extension('half-orm-x', '1.0.0')

        assert exc.value.code == 1
        mock_trust.assert_not_called()

    def test_missing_stdin_is_not_interactive(self):
        with patch('half_orm.cli.sys.stdin', None):
            assert half_orm_cli._stdin_is_interactive() is False

    def test_closed_stdin_is_not_interactive(self):
        stream = Mock()
        stream.isatty.side_effect = ValueError('I/O operation on closed file')
        with patch('half_orm.cli.sys.stdin', stream):
            assert half_orm_cli._stdin_is_interactive() is False


class TestOfficialExtensionList:
    """An unclaimed name on the allowlist is a free pass to whoever takes it."""

    def test_test_extension_is_not_official(self):
        """half-orm-test-extension is unregistered on PyPI, so squattable."""
        assert is_official_extension('half-orm-test-extension') is False
        assert is_official_extension('half_orm_test_extension') is False

    def test_maintained_extensions_are_official(self):
        for name in ('half-orm-inspect', 'half-orm-gen', 'half-orm-dev'):
            assert is_official_extension(name) is True


class TestPreCheck:
    """Test pre_check hook in the extension mechanism."""

    @pytest.fixture(autouse=True)
    def _fabricated_distributions_own_their_modules(self):
        with identity_checks_satisfied():
            yield

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