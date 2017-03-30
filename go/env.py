#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Can be used to point environment variable to hermetic Go toolset.

Usage (on linux and mac):
$ eval `./env.py`
$ go version

Or it can be used to wrap a command:

$ ./env.py go version
"""

assert __name__ == '__main__'

import argparse
import imp
import os
import pipes
import subprocess
import sys


# Do not want to mess with sys.path, load the module directly.
bootstrap = imp.load_source(
    'bootstrap', os.path.join(os.path.dirname(__file__), 'bootstrap.py'))

old = os.environ.copy()

def _escape_special(v):
  """Returns (str): The supplied value, with special shell characters escaped.

  Replace special characters with their escaped form. This will allow them
  to be interpreted by the shell using the $'...' notation.

  Args:
    v (str): The input value to escape.
  """
  for f, r in (
      ('\n', '\\n'),
      ('\b', '\\b'),
      ('\r', '\\r'),
      ('\t', '\\t'),
      ('\v', '\\v')):
    v = v.replace(f, r)
  return v


if sys.platform == 'win32':
  def emit_env_var(key, value):
    # TODO: The quoting here is probably insufficient for all corner cases.
    # We strip "'" because cmd.exe doesn't like it in PATH for some reason.
    print 'set %s=%s' % (key, pipes.quote(value).strip("'"))
else:
  def emit_env_var(key, value):
    orig_value, value = value, _escape_special(value)
    # We will only use the $'...' notation if there was an escaped character
    # in the string.
    print 'export %s=%s%s' % (key, ('$') if orig_value != value else (''),
                              pipes.quote(value))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--preserve-gopath', action='store_true',
      help='Preserve the existing GOPATH, appending to it instead of '
           'overwriting it.')
  parser.add_argument('--toolset-root', action='store', metavar='PATH',
      help='Use this path for the toolset root instead of deafult.')
  parser.add_argument('--deps-only', action='store_true',
      help='If True, only download and install dependencies in "deps" files.')

  args, extras = parser.parse_known_args()
  if extras and extras[0] == '--':
    extras.pop(0)

  new = bootstrap.prepare_go_environ(
      preserve_gopath=args.preserve_gopath,
      toolset_root=args.toolset_root,
      deps_only=args.deps_only)
  if not extras:
    for key, value in sorted(new.iteritems()):
      if old.get(key) != value:
        emit_env_var(key, value)
  else:
    exe = extras[0]
    if exe == 'python':
      exe = sys.executable
    else:
      # Help Windows to find the executable in new PATH, do it only when
      # executable is referenced by name (and not by path).
      if os.sep not in exe:
        exe = bootstrap.find_executable(exe, [bootstrap.WORKSPACE])
    sys.exit(subprocess.call([exe] + extras[1:], env=new))


assert __name__ == '__main__'
main()
