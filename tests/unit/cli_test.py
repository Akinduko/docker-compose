from __future__ import unicode_literals
from __future__ import absolute_import
import logging
import os
from .. import unittest

from fig.cli import main
from fig.cli.main import TopLevelCommand
from six import StringIO


class CLITestCase(unittest.TestCase):
    def test_default_project_name(self):
        cwd = os.getcwd()

        try:
            os.chdir('tests/fixtures/simple-figfile')
            command = TopLevelCommand()
            self.assertEquals('simplefigfile', command.project_name)
        finally:
            os.chdir(cwd)

    def test_project_name_with_explicit_base_dir(self):
        command = TopLevelCommand()
        command.base_dir = 'tests/fixtures/simple-figfile'
        self.assertEquals('simplefigfile', command.project_name)

    def test_project_name_with_explicit_project_name(self):
        command = TopLevelCommand()
        command.explicit_project_name = 'explicit-project-name'
        self.assertEquals('explicitprojectname', command.project_name)

    def test_yaml_filename_check(self):
        command = TopLevelCommand()
        command.base_dir = 'tests/fixtures/longer-filename-figfile'
        self.assertTrue(command.project.get_service('definedinyamlnotyml'))

    def test_help(self):
        command = TopLevelCommand()
        with self.assertRaises(SystemExit):
            command.dispatch(['-h'], None)

    def test_setup_logging(self):
        main.setup_logging()
        self.assertEqual(logging.getLogger().level, logging.DEBUG)
        self.assertEqual(logging.getLogger('requests').propagate, False)
