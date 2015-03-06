#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Code supporting run.py implementation.

Reused across infra/run.py and infra_internal/run.py.
"""

import os
import sys


def boot_venv(script, env_path):
  """Reexecs the top-level script in a virtualenv (if necessary)."""
  RUN_PY_RECURSION_BLOCKER = 'RUN_PY_RECURSION'

  if os.path.abspath(sys.prefix) != env_path:
    if RUN_PY_RECURSION_BLOCKER in os.environ:
      print >> sys.stderr, 'TOO MUCH RECURSION IN RUN.PY'
      sys.exit(-1)

    # not in the venv
    if sys.platform.startswith('win'):
      python = os.path.join(env_path, 'Scripts', 'python.exe')
    else:
      python = os.path.join(env_path, 'bin', 'python')
    if os.path.exists(python):
      os.environ[RUN_PY_RECURSION_BLOCKER] = "1"
      os.environ.pop('PYTHONPATH', None)
      os.execv(python, [python, script] + sys.argv[1:])
      print >> sys.stderr, "Exec is busted :("
      sys.exit(-1)  # should never reach

    print 'You must use the virtualenv in ENV for scripts in the infra repo.'
    print 'Running `gclient runhooks` will create this environment for you.'
    sys.exit(1)

  # In case some poor script ends up calling run.py, don't explode them.
  os.environ.pop(RUN_PY_RECURSION_BLOCKER, None)


def run_py_main(args, runpy_path, env_path, package):
  boot_venv(runpy_path, env_path)

  import argparse
  import runpy
  import shlex
  import textwrap

  import argcomplete

  os.chdir(os.path.dirname(runpy_path))

  # Impersonate the argcomplete 'protocol'
  completing = os.getenv('_ARGCOMPLETE') == '1'
  if completing:
    assert not args
    line = os.getenv('COMP_LINE')
    args = shlex.split(line)[1:]
    if len(args) == 1 and not line.endswith(' '):
      args = []

  if not args or not args[0].startswith('%s.' % package):
    commands = []
    for root, _, files in os.walk(package):
      if '__main__.py' in files:
        commands.append(root.replace(os.path.sep, '.'))

    if completing:
      # Argcomplete is listening for strings on fd 8
      with os.fdopen(8, 'wb') as f:
        print >> f, '\n'.join(commands)
      return

    print textwrap.dedent("""\
    usage: run.py %s.<module.path.to.tool> [args for tool]

    %s

    Available tools are:""") % (
        package, sys.modules['__main__'].__doc__.strip())
    for command in commands:
      print '  *', command
    return 1

  if completing:
    to_nuke = ' ' + args[0]
    os.environ['COMP_LINE'] = os.environ['COMP_LINE'].replace(to_nuke, '', 1)
    os.environ['COMP_POINT'] = str(int(os.environ['COMP_POINT']) - len(to_nuke))
    orig_parse_args = argparse.ArgumentParser.parse_args
    def new_parse_args(self, *args, **kwargs):
      argcomplete.autocomplete(self)
      return orig_parse_args(*args, **kwargs)
    argparse.ArgumentParser.parse_args = new_parse_args
  else:
    # remove the module from sys.argv
    del sys.argv[1]

  runpy.run_module(args[0], run_name='__main__', alter_sys=True)
