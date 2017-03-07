# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Attempts to remove references to Conda installation directory to make the
environment more relocatable in exchange for its modifiability.

No new package can be installed into a butchered environment.

Works great on Mac and Win, but doesn't really makes the environment prefix
independent on Linux, since Linux binaries like to have prefix hardcoded.

Everything seems to work even on Linux though, but watch out for weirdness.

Helpful links:
  https://github.com/conda/conda-recipes
  http://conda.pydata.org/docs/building/meta-yaml.html#relocatable
"""

import ast
import glob
import os
import shutil
import sys


IS_WIN = sys.platform in ('win32', 'cygwin')


def main(conda_dir):
  butcher_bin(conda_dir)
  butcher_conda_meta(conda_dir)
  butcher_include(conda_dir)
  butcher_lib(conda_dir)
  butcher_pkgs(conda_dir)
  butcher_pyqt(conda_dir)


def butcher_bin(conda_dir):
  if IS_WIN:
    bin_dir = os.path.join(conda_dir, 'Library', 'bin')
  else:
    bin_dir = os.path.join(conda_dir, 'bin')

  whitelist = [
    'python', # relative symlink to python2.7, keep it, it's cute
  ]
  blacklist = [
    'c_rehash',        # perl script with references to local prefix
    'cairo-trace',     # not needed
    'freetype-config', # we won't be linking to freetype
    'libpng16-config', # same
    'xml2-config',     # same
    'pyuic4',          # just use PyQt4/uic/pyuic.py directly
    'pyuic4.bat',      # same
    'qt.conf',         # Qt manages to work without it
  ]

  def is_naughty_shell_script(path):
    """True if script's shebang points to local prefix."""
    if IS_WIN:
      return False
    with open(path, 'r') as f:
      return f.read(1024).startswith('#!' + bin_dir)

  # Remove meaningless symlinks and shell scripts that'll broke when relocated.
  # 'python' stays, it is all that matters.
  for p in os.listdir(bin_dir):
    full = os.path.join(bin_dir, p)
    kill_it = not (p in whitelist or os.path.isdir(full)) and (
      p in blacklist or
      os.path.islink(full) or
      is_naughty_shell_script(full))
    if kill_it:
      kill_file(full)


def butcher_conda_meta(conda_dir):
  # 'conda-meta' contains history of local commands with full paths, as well
  # as ton of *.json files referencing local paths. We aren't going to install
  # any more conda packages, no need for meta files.
  kill_dir(os.path.join(conda_dir, 'conda-meta'))


def butcher_include(conda_dir):
  # Header files? Where we're going we don't need header files.
  # But in case we do, a special care must be given to openssl/opensslconf.h,
  # it references local prefix.
  kill_dir(os.path.join(conda_dir, 'include'))


def butcher_lib(conda_dir):
  if IS_WIN:
    lib = os.path.join(conda_dir, 'Library', 'lib')
  else:
    lib = os.path.join(conda_dir, 'lib')

  # We aren't going to build Tk\Tcl extensions, it's not 80s.
  kill_file(os.path.join(lib, 'tclConfig.sh'))
  kill_file(os.path.join(lib, 'tkConfig.sh'))

  # That's all for Win.
  if IS_WIN:
    return

  # We won't be using cmake.
  kill_dir(os.path.join(lib, 'cmake'))

  # We aren't going to build C stuff, kill libtool and pkg-config files.
  kill_glob(os.path.join(lib, '*.la'))
  kill_glob(os.path.join(lib, 'cairo', '*.la'))
  kill_dir(os.path.join(lib, 'pkgconfig'))

  # We aren't be building python extensions at all, in fact.
  kill_file(os.path.join(lib, 'python2.7', 'config', 'Makefile'))

  # This file looks important, let's patch it instead of removing.
  sysconf = os.path.join(lib, 'python2.7', '_sysconfigdata.py')
  if patch_file(sysconf, conda_dir):
    kill_file(os.path.join(lib, 'python2.7', '_sysconfigdata.pyc'))
    kill_file(os.path.join(lib, 'python2.7', '_sysconfigdata.pyo'))


def butcher_pkgs(conda_dir):
  # pkgs contains unpacked Conda packages that act as source of hardlinks that
  # gets installed into actual prefix. Since its hard links, it's OK to remove
  # originals (thus "converting" hardlinks into regular files).
  kill_dir(os.path.join(conda_dir, 'pkgs')) # TODO: Windows?


def butcher_pyqt(conda_dir):
  if IS_WIN:
    prefix = os.path.join(conda_dir, 'Library')
  else:
    prefix = conda_dir

  # We won't be using qmake.
  kill_glob(os.path.join(prefix, 'lib', '*.prl'))
  kill_dir(os.path.join(prefix, 'mkspecs'))

  # We don't care about Qt4 tests.
  kill_dir(os.path.join(prefix, 'tests', 'qt4'))

  if not IS_WIN:
    # We won't by using PyQt build system.
    kill_file(
        os.path.join(
            conda_dir, 'lib', 'python2.7', 'site-packages', 'sipconfig.py'))

    # This file looks important, let's patch it instead.
    patch_file(
        os.path.join(
            conda_dir, 'lib', 'python2.7', 'site-packages',
            'PyQt4', 'pyqtconfig.py'),
        conda_dir)
  else:
    kill_file(os.path.join(conda_dir, 'qt.conf'))


###


def patch_file(path, prefix):
  """Replaces references to 'prefix' with '/opt/fake-python-prefix'."""
  with open(path, 'rb') as f:
    blob = f.read()
  if prefix.endswith('/') or prefix.endswith('\\'):
    prefix = prefix[:-1]
  if IS_WIN:
    fake_prefix = 'C:\\fake-python-prefix'
  else:
    fake_prefix = '/opt/fake-python-prefix'
  modified = blob.replace(prefix, fake_prefix)
  if modified != blob:
    print 'Patching %s' % os.path.basename(path)
    with open(path, 'wb') as f:
      f.write(modified)
    return True
  return False


def kill_file(path):
  if os.path.exists(path) or os.path.lexists(path):
    print 'Removing %s' % os.path.basename(path)
    os.remove(path)


def kill_dir(path):
  if os.path.exists(path):
    print 'Removing %s directory' % os.path.basename(path)
    shutil.rmtree(path)


def kill_glob(path):
  for p in glob.glob(path):
    kill_file(p)


if __name__ == '__main__':
  sys.exit(main(os.path.abspath(sys.argv[1])))
