#!/usr/bin/env vpython
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
  args = sys.argv[1:]
  if args and args[0] == '--':
    args.pop(0)

  new = bootstrap.prepare_go_environ()
  if not args:
    for key, value in sorted(new.iteritems()):
      if old.get(key) != value:
        emit_env_var(key, value)
    # VIRTUAL_ENV is added by the vpython wrapper. It usually *does not* exist
    # in os.environ of the outer shell that executes eval `./env.py`. Since we
    # are about to replace the native python in PATH with virtualenv's one, we
    # must also make sure the new environment has VIRTUAL_ENV set. Otherwise
    # some virtualenv-aware tools (like gcloud) get confused.
    #
    # Note that once env.py finishes execution, nothing is holding a lock on
    # vpython virtualenv directory, and it may eventually be garbage collected
    # (while the user is still inside a shell that references it). We assume it
    # is rare, and the users can manually recover (by reexecuting env.py). This
    # won't be happening on bots, since they don't use eval `./env.py`.
    if 'VIRTUAL_ENV' in old:
      emit_env_var('VIRTUAL_ENV', old['VIRTUAL_ENV'])
  else:
    exe = args[0]
    if exe == 'python':
      exe = sys.executable
    else:
      # Help Windows to find the executable in new PATH, do it only when
      # executable is referenced by name (and not by path).
      if os.sep not in exe:
        exe = bootstrap.find_executable(exe, [bootstrap.WORKSPACE])
    sys.exit(subprocess.call([exe] + args[1:], env=new))


assert __name__ == '__main__'
main()
