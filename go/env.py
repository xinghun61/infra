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

import imp
import os
import pipes
import subprocess
import sys


# Do not want to mess with sys.path, load the module directly.
bootstrap = imp.load_source(
    'bootstrap', os.path.join(os.path.dirname(__file__), 'bootstrap.py'))

old = os.environ.copy()
new = bootstrap.prepare_go_environ()


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
  if len(sys.argv) == 1:
    for key, value in sorted(new.iteritems()):
      if old.get(key) != value:
        emit_env_var(key, value)
  else:
    exe = sys.argv[1]
    if exe == 'python':
      exe = sys.executable
    else:
      # Help Windows to find the executable in new PATH, do it only when
      # executable is referenced by name (and not by path).
      if os.sep not in exe:
        exe = bootstrap.find_executable(exe, [bootstrap.WORKSPACE])
    sys.exit(subprocess.call([exe] + sys.argv[2:], env=new))


assert __name__ == '__main__'
main()