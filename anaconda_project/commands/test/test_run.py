# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from copy import deepcopy
import errno
import platform
import os

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.commands.run import run_command, main
from anaconda_project.commands.prepare_with_mode import UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

from anaconda_project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.project = "."
        self.env_spec = None
        self.mode = UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
        self.command = None
        self.extra_args_for_command = None
        for key in kwargs:
            setattr(self, key, kwargs[key])


python_exe = "python"
if platform.system() == 'Windows':
    python_exe = "python.exe"


def test_run_command(monkeypatch):

    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    mock_environ = deepcopy(os.environ)
    mock_environ['FOO'] = 'bar'

    monkeypatch.setattr('os.environ', mock_environ)
    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run(dirname):
        project_dir_disable_dedicated_env(dirname)

        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command=None,
                             extra_command_args=None)
        assert result is None
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]
        assert 'bar' == executed['env']['FOO']

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}

commands:
  default:
    conda_app_entry: python --version

"""}, check_run)


def test_run_command_no_app_entry(capsys):
    def check_run_no_app_entry(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command=None,
                             extra_command_args=None)
        assert result is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """

"""}, check_run_no_app_entry)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'No known run command' in err


def test_run_command_nonexistent_project(capsys):
    def check_run_nonexistent(dirname):
        project_dir = os.path.join(dirname, "nope")
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--project', project_dir])

        assert 1 == result

        out, err = capsys.readouterr()
        assert out == ""
        assert ("Project directory '%s' does not exist." % project_dir) in err

    with_directory_contents(dict(), check_run_nonexistent)


def test_run_command_failed_prepare(capsys):
    def check_run_failed_prepare(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command=None,
                             extra_command_args=None)
        assert result is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  - WILL_NOT_BE_SET
"""}, check_run_failed_prepare)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'Environment variable WILL_NOT_BE_SET is not set' in err


def test_main(monkeypatch, capsys):
    def mock_conda_create(prefix, pkgs, channels):
        raise RuntimeError("this test should not create an environment in %s with pkgs %r" % (prefix, pkgs))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(project=dirname))

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_main_failed_exec(monkeypatch, capsys):
    def mock_execvpe(file, args, env):
        raise OSError(errno.ENOMEM, "It did not work, Michael")

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(project=dirname))

        assert 1 == result

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert 'Failed to execute' in err
    assert 'It did not work, Michael' in err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_run_command_extra_args(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--project', dirname, 'default', 'foo',
                                                 '$PATH', '--something'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert len(executed['args']) == 5
        assert '--version' == executed['args'][1]
        assert 'foo' == executed['args'][2]
        assert '$PATH' == executed['args'][3]
        assert '--something' == executed['args'][4]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_run_command_extra_args_with_double_hyphen(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        # double hyphen lets us specify "--foo" as a command name
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--project', dirname, '--', '--foo', '--bar'
                                                 ])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert len(executed['args']) == 3
        assert '--version' == executed['args'][1]
        assert '--bar' == executed['args'][2]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  "--foo":
    conda_app_entry: python --version
"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def _test_run_command_foo(command_line, monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['args'][1:]

    return with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version def
  foo:
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""}, check_run_main)


def test_run_command_specify_name_after_options(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--project', '<DIRNAME>', 'foo'], monkeypatch, capsys)

    assert args == ['--version', 'foo']


def test_run_command_specify_name_before_options(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', 'foo', '--project', '<DIRNAME>'], monkeypatch, capsys)
    assert args[:-1] == ['--version', 'foo', '--project']


def test_run_command_omit_name_use_default(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--project', '<DIRNAME>'], monkeypatch, capsys)
    assert args == ['--version', 'def']


def test_run_command_nonexistent_name(monkeypatch, capsys):
    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--project', dirname, 'nope'])

        assert 1 == result

        out, err = capsys.readouterr()
        assert "" == out
        assert (("Command name 'nope' is not in %s, these names were found: bar, default, foo\n") %
                (os.path.join(dirname, 'project.yml'))) == err

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version
  foo:
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""}, check_run_main)
