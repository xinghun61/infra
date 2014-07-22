#!ENV/bin/python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper for `python -m` to make running tools simpler.

A tool is defined as a python module with a __main__.py file. This latter file
is run by the present script.

In particular, allows gclient to change directories when running hooks for
infra.
"""

assert __name__ == '__main__'

import argparse
import os
import runpy
import shlex
import sys
import textwrap


ROOT = os.path.dirname(os.path.abspath(__file__))

if os.path.abspath(sys.prefix) != os.path.join(ROOT, 'ENV'):
  print 'You must use the virtualenv in ENV for scripts in the infra repo.'
  print 'Please run this as `./ENV/bin/python run.py`. If you do not have an'
  print 'ENV directory, please make one with `gclient runhooks`.'
  sys.exit(1)


import argcomplete


def main(args):
  os.chdir(os.path.dirname(os.path.abspath(__file__)))

  # Impersonate the argcomplete 'protocol'
  completing = os.getenv('_ARGCOMPLETE') == '1'
  if completing:
    assert not args
    line = os.getenv('COMP_LINE')
    args = shlex.split(line)[1:]
    if len(args) == 1 and not line.endswith(' '):
      args = []

  if not args or not args[0].startswith('infra.'):
    commands = []
    for root, _, files in os.walk('infra'):
      if '__main__.py' in files:
        commands.append(root.replace(os.path.sep, '.'))

    if completing:
      # Argcomplete is listening for strings on fd 8
      with os.fdopen(8, 'wb') as f:
        print >> f, '\n'.join(commands)
      return

    print textwrap.dedent("""\
    usage: run.py infra.<module.path.to.tool> [args for tool]

    %s

    Available tools are:""") % __doc__.strip()
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


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
