"""
Tests pour half_orm/__main__.py

Tests basés sur le VRAI code source avec les vraies fonctions.
"""

import pytest
import subprocess
import sys
import os
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import tempfile
import shutil

import psycopg

from half_orm import model_errors


class TestMainModule:
    """Tests pour python -m half_orm (subprocess)"""
    
    def test_main_module_runs(self):
        """Test que python -m half_orm s'exécute sans erreur"""
        result = subprocess.run(
            [sys.executable, "-m", "half_orm"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Doit s'exécuter sans crash
        assert result.returncode == 0
        # Doit afficher la version
        assert "[halfORM] version" in result.stdout
    
    def test_main_module_with_help(self):
        """Test python -m half_orm --help"""
        result = subprocess.run(
            [sys.executable, "-m", "half_orm", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "Examples:" in result.stdout
        assert "Documentation:" in result.stdout
    
    def test_main_module_with_database_arg(self):
        """Test python -m half_orm database_name"""
        result = subprocess.run(
            [sys.executable, "-m", "half_orm", "nonexistent_db"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Doit afficher la version même si la DB échoue
        assert "[halfORM] version" in result.stdout
        # Peut échouer avec returncode 1 si la DB n'existe pas
        assert "Error connecting to database" in result.stderr or result.returncode == 0
    
    def test_main_module_with_table_arg(self):
        """Test python -m half_orm database_name schema.table"""
        result = subprocess.run(
            [sys.executable, "-m", "half_orm", "test_db", "public.test_table"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Doit afficher la version
        assert "[halfORM] version" in result.stdout
        # Peut échouer si la DB/table n'existe pas
        assert "Error" in result.stderr or result.returncode == 0


class TestIndividualFunctions:
    """Tests des fonctions individuelles"""
    
    @patch('builtins.print')
    def test_show_version(self, mock_print):
        """Test show_version()"""
        from half_orm.__main__ import show_version
        import half_orm
        
        show_version()
        
        mock_print.assert_called_once_with(f"[halfORM] version {half_orm.__version__}")
    
    @patch('builtins.print')
    def test_print_help(self, mock_print):
        """Test print_help()"""
        from half_orm.__main__ import print_help
        import half_orm
        
        print_help()
        
        # Vérifie que toutes les sections d'aide sont affichées
        printed_lines = [call[0][0] for call in mock_print.call_args_list if call[0]]
        printed_text = '\n'.join(str(line) for line in printed_lines)
        
        assert f"[halfORM] version {half_orm.__version__}" in printed_text
        assert "Usage:" in printed_text
        assert "Examples:" in printed_text
        assert "Documentation:" in printed_text
        assert "python -m half_orm" in printed_text
    
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    def test_check_peer_authentication_success(self, mock_print, mock_model):
        """Test check_peer_authentication() avec succès"""
        from half_orm.__main__ import check_peer_authentication
        
        # Mock connexion réussie
        mock_model.return_value = MagicMock()
        
        check_peer_authentication()
        
        mock_model.assert_called_once_with('template1')
        mock_print.assert_called_once_with("✅ Connected to template1 database (default setup)")
    
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    def test_check_peer_authentication_failure(self, mock_print, mock_model):
        """Test check_peer_authentication() avec échec"""
        from half_orm.__main__ import check_peer_authentication
        
        # Mock connexion échouée
        error_msg = "peer authentication failed"
        mock_model.side_effect = psycopg.OperationalError(error_msg)
        
        check_peer_authentication()
        
        mock_model.assert_called_once_with('template1')
        mock_print.assert_called_once_with(f"⚠️  Unable to connect to template1: {error_msg}.")

    @patch('half_orm.__main__.listdir')
    @patch('half_orm.__main__.path')
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    @patch('sys.stderr')    
    def test_check_databases_access_with_files(self, mock_stderr, mock_print, mock_model, mock_path, mock_listdir):
        """Test check_databases_access() avec fichiers de config"""
        from half_orm.__main__ import check_databases_access
        
        # Mock des fichiers dans le répertoire
        mock_listdir.return_value = ['db1', 'db2', 'not_a_file']
        mock_path.isfile.return_value = True
        mock_path.join.side_effect = lambda dir, file: f"{dir}/{file}"

        # Mock connexions: db1 réussit, db2 échoue
        def mock_model_side_effect(name):
            if name == 'db1':
                return MagicMock()
            else:
                raise psycopg.OperationalError("Connection failed")
        
        mock_model.side_effect = mock_model_side_effect

        check_databases_access()
        
        # Vérifie les tentatives de connexion
        mock_model.assert_any_call('db1')
        mock_model.assert_any_call('db2')
        
        # Vérifie les messages de succès et d'erreur
        success_calls = [call for call in mock_print.call_args_list if '✅ db1' in str(call)]
        assert len(success_calls) == 1
        
        error_calls = [call for call in mock_stderr.write.call_args_list if '❌ db2' in str(call)]
        assert len(error_calls) == 1
    
    @patch('half_orm.model.CONF_DIR', '/test/conf/dir')
    @patch('half_orm.__main__.listdir')
    @patch('half_orm.__main__.path')
    @patch('builtins.print')
    def test_check_databases_access_no_files(self, mock_print, mock_isfile, mock_listdir):
        """Test check_databases_access() sans fichiers de config"""
        from half_orm.__main__ import check_databases_access
        
        # Mock répertoire vide
        mock_listdir.return_value = []
        
        check_databases_access()
        
        # Vérifie le message informatif
        printed_lines = [str(call) for call in mock_print.call_args_list]
        no_files_message = any("No database configuration files found" in line for line in printed_lines)
        assert no_files_message
    
    @patch('half_orm.model.CONF_DIR', '/nonexistent/dir')
    @patch('half_orm.__main__.listdir')
    @patch('sys.stderr')
    @patch('builtins.print')
    def test_check_databases_access_no_directory(self, mock_print, mock_stderr, mock_listdir):
        """Test check_databases_access() avec répertoire inexistant"""
        from half_orm.__main__ import check_databases_access
        
        # Mock répertoire inexistant
        mock_listdir.side_effect = FileNotFoundError("Directory not found")
        
        check_databases_access()
        
        # Vérifie le message d'erreur
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "does not exist" in str(call)]
        assert len(error_calls) >= 1


class TestMainFunction:
    """Tests de la fonction main() avec différents arguments"""
    
    @patch('sys.argv', ['half_orm'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.check_peer_authentication')
    @patch('half_orm.__main__.check_databases_access')
    def test_main_no_args(self, mock_check_db, mock_check_peer, mock_show_version):
        """Test main() sans arguments (mode diagnostic)"""
        from half_orm.__main__ import main
        
        main()
        
        mock_show_version.assert_called_once()
        mock_check_peer.assert_called_once()
        mock_check_db.assert_called_once()
    
    @patch('sys.argv', ['half_orm', '--help'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.print_help')
    def test_main_help_flag(self, mock_print_help, mock_show_version):
        """Test main() avec --help"""
        from half_orm.__main__ import main
        
        main()
        
        mock_show_version.assert_called_once()
        mock_print_help.assert_called_once()
    
    @patch('sys.argv', ['half_orm', '-h'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.print_help')
    def test_main_help_short(self, mock_print_help, mock_show_version):
        """Test main() avec -h"""
        from half_orm.__main__ import main
        
        main()
        
        mock_show_version.assert_called_once()
        mock_print_help.assert_called_once()
    
    @patch('sys.argv', ['half_orm', 'help'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.print_help')
    def test_main_help_word(self, mock_print_help, mock_show_version):
        """Test main() avec 'help'"""
        from half_orm.__main__ import main
        
        main()
        
        mock_show_version.assert_called_once()
        mock_print_help.assert_called_once()
    
    @patch('sys.argv', ['half_orm', 'test_db'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    def test_main_database_arg_success(self, mock_print, mock_model, mock_show_version):
        """Test main() avec argument database (succès)"""
        from half_orm.__main__ import main
        
        # Mock modèle réussi
        mock_instance = MagicMock()
        mock_instance.__str__ = MagicMock(return_value="Database structure")
        mock_model.return_value = mock_instance
        
        main()
        
        mock_show_version.assert_called_once()
        mock_model.assert_called_once_with('test_db')
        mock_print.assert_called_once_with(mock_instance)
    
    @patch('sys.argv', ['half_orm', 'invalid_db'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.Model')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_main_database_arg_failure(self, mock_exit, mock_stderr, mock_model, mock_show_version):
        """Test main() avec database invalide"""
        from half_orm.__main__ import main
        
        # Mock échec de connexion
        mock_model.side_effect = psycopg.OperationalError("Connection failed")
        
        main()
        
        mock_show_version.assert_called_once()
        mock_model.assert_called_once_with('invalid_db')
        
        # Vérifie qu'on écrit l'erreur et qu'on exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Error connecting to database" in str(call)]
        assert len(error_calls) >= 1
        mock_exit.assert_called_once_with(1)
    
    @patch('sys.argv', ['half_orm', 'test_db', 'schema.table'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    def test_main_relation_arg_success(self, mock_print, mock_model, mock_show_version):
        """Test main() avec arguments database et relation (succès)"""
        from half_orm.__main__ import main
        
        # Mock modèle et relation
        mock_relation_instance = MagicMock()
        mock_relation_instance.__str__ = MagicMock(return_value="Table details")
        
        mock_relation_class = MagicMock()
        mock_relation_class.return_value = mock_relation_instance
        
        mock_model_instance = MagicMock()
        mock_model_instance.get_relation_class.return_value = mock_relation_class
        mock_model.return_value = mock_model_instance
        
        main()
        
        mock_show_version.assert_called_once()
        mock_model.assert_called_once_with('test_db')
        mock_model_instance.get_relation_class.assert_called_once_with('schema.table')
        mock_print.assert_called_once_with(mock_relation_instance)
    
    @patch('sys.argv', ['half_orm', 'test_db', 'invalid.table'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.Model')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_main_relation_arg_failure(self, mock_exit, mock_stderr, mock_model, mock_show_version):
        """Test main() avec relation invalide"""
        from half_orm.__main__ import main
        
        # Mock modèle OK mais relation échoue
        mock_model_instance = MagicMock()
        mock_model_instance.get_relation_class.side_effect = model_errors.UnknownRelation(('test_db', 'invalid', 'table'))
        mock_model.return_value = mock_model_instance
        
        main()
        
        mock_show_version.assert_called_once()
        mock_model.assert_called_once_with('test_db')
        
        # Vérifie l'erreur et exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Error accessing relation" in str(call)]
        assert len(error_calls) >= 1
        mock_exit.assert_called_once_with(1)
    
    @patch('sys.argv', ['half_orm', 'arg1', 'arg2', 'arg3', 'arg4'])
    @patch('half_orm.__main__.show_version')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_main_too_many_args(self, mock_exit, mock_stderr, mock_show_version):
        """Test main() avec trop d'arguments"""
        from half_orm.__main__ import main
        
        main()
        
        mock_show_version.assert_called_once()
        
        # Vérifie l'erreur "Too many arguments"
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Too many arguments" in str(call)]
        assert len(error_calls) >= 1
        mock_exit.assert_called_once_with(1)


class TestEdgeCases:
    """Tests des cas limites et edge cases"""
    
    @patch('sys.argv', ['half_orm', 'db_with_unicode_🎉'])
    @patch('half_orm.__main__.show_version')
    @patch('half_orm.__main__.Model')
    @patch('builtins.print')
    def test_unicode_database_name(self, mock_print, mock_model, mock_show_version):
        """Test avec nom de base contenant unicode"""
        from half_orm.__main__ import main
        
        mock_model.return_value = MagicMock()
        
        main()
        
        mock_model.assert_called_once_with('db_with_unicode_🎉')
    
    @patch('sys.argv', ['half_orm', ''])
    @patch('half_orm.__main__.show_version')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_empty_database_name(self, mock_exit, mock_stderr, mock_show_version):
        """Test avec nom de base vide"""
        from half_orm.__main__ import main
        
        main()

        # Vérifie qu'on écrit l'erreur et qu'on exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Empty database name" in str(call)]
        assert len(error_calls) >= 1
        assert call(1) in mock_exit.call_args_list
    
    @patch('sys.argv', ['half_orm', 'db', ''])
    @patch('half_orm.__main__.show_version')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_empty_relation_name(self, mock_exit, mock_stderr, mock_show_version):
        """Test avec nom de relation vide"""
        from half_orm.__main__ import main
        
        main()
        
        # Vérifie qu'on écrit l'erreur et qu'on exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Empty relation name" in str(call)]
        assert len(error_calls) >= 1
        assert call(1) in mock_exit.call_args_list


    @patch('sys.argv', ['half_orm', '', 'x.y'])
    @patch('half_orm.__main__.show_version')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_empty_database_name_with_relation_name(self, mock_exit, mock_stderr, mock_show_version):
        """Test avec nom de db vide mais un nom de relation"""
        from half_orm.__main__ import main
        
        main()
        
        # Vérifie qu'on écrit l'erreur et qu'on exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Empty database name" in str(call)]
        assert len(error_calls) >= 1
        assert call(1) in mock_exit.call_args_list


    @patch('sys.argv', ['half_orm', '', ''])
    @patch('half_orm.__main__.show_version')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_empty_relation_name_and_db_name(self, mock_exit, mock_stderr, mock_show_version):
        """Test avec noms de db et de relation vides"""
        from half_orm.__main__ import main
        
        main()
        
        # Vérifie qu'on écrit l'erreur et qu'on exit(1)
        error_calls = [call for call in mock_stderr.write.call_args_list 
                      if "Empty database name" in str(call)]
        assert len(error_calls) >= 1
        assert call(1) in mock_exit.call_args_list


class TestIntegrationWithRealEnvironment:
    """Tests d'intégration avec environnement simulé"""
    
    def setup_method(self):
        """Setup pour chaque test d'intégration"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_conf_dir = Path(self.temp_dir) / "half_orm_conf"
        self.temp_conf_dir.mkdir()
    
    def teardown_method(self):
        """Cleanup après chaque test"""
        shutil.rmtree(self.temp_dir)
    
    @patch('half_orm.model.CONF_DIR')
    @patch('half_orm.__main__.Model')
    def test_check_databases_access_integration(self, mock_model, mock_conf_dir):
        """Test d'intégration avec vrais fichiers de config"""
        from half_orm.__main__ import check_databases_access
        
        # Setup environnement temporaire
        mock_conf_dir.__str__ = lambda: str(self.temp_conf_dir)
        mock_conf_dir.__fspath__ = lambda: str(self.temp_conf_dir)
        
        # Patch la constante
        with patch('half_orm.__main__.CONF_DIR', str(self.temp_conf_dir)):
            # Crée des fichiers de config factices
            (self.temp_conf_dir / "test_db1").write_text("[database]\nname=test_db1")
            (self.temp_conf_dir / "test_db2").write_text("[database]\nname=test_db2")
            
            # Mock des connexions réussies
            mock_model.return_value = MagicMock()
            
            # Capture de l'output
            with patch('builtins.print') as mock_print:
                check_databases_access()
            
            # Vérifie qu'on teste les deux databases
            assert mock_model.call_count == 2
            mock_model.assert_any_call('test_db1')
            mock_model.assert_any_call('test_db2')


if __name__ == "__main__":
    pytest.main([__file__])