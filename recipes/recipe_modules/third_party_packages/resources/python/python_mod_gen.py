#!/usr/bin/python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This script generates a Python build "Setup.local" file that describes a fully-
static Python module layout.

It does this by:
  - Probing the local Python installation for all of the modules that it is
    configured to emit.
  - Transforming the extension objects into Setup.local file.
  - Augmenting that file based on external instructions to complete the linking.

This script is intended to be run by the Python build interpreter. If it is
run by a system Python, make sure that Python uses "-s" and "-S" flags to
remove the influence of the local system's site configuration.
"""

import argparse
import contextlib
import os
import sys


def log(f, *arg):
  print >>sys.stderr, f % arg


def get_build_dir(root):
  with open(os.path.join(root, 'pybuilddir.txt')) as fd:
    return fd.read().strip()


@contextlib.contextmanager
def _insert_sys_path(*v):
  orig = sys.path[:]
  try:
    sys.path = list(v) + sys.path
    yield
  finally:
    sys.path = orig


@contextlib.contextmanager
def _temp_sys_argv(v):
  orig = sys.argv
  try:
    sys.argv = v
    yield
  finally:
    sys.argv = orig


@contextlib.contextmanager
def _temp_sys_builtins(*v):
  orig = sys.builtin_module_names
  try:
    sys.builtin_module_names = list(v)
    yield
  finally:
    sys.builtin_module_names = orig


@contextlib.contextmanager
def _temp_sys_executable(v):
  orig = sys.executable
  try:
    sys.executable = v
    yield
  finally:
    sys.executable = orig


def _get_extensions(root, build_dir):
  lib_dir = os.path.join(root, 'Lib')

  # Create a path to the "build Python" executable. This is the path that the
  # "setup.py" would expect to be invoked with. It doesn't really matter if this
  # file actually exists (e.g., on Mac it would be "python.exe").
  build_python = os.path.join(root, 'python')

  # Enter a "setup.py" expected library pathing, and tell distutil we want to
  # build extensions.
  with _temp_sys_builtins(), _temp_sys_executable(build_python):
    with \
        _temp_sys_argv(['python', 'build_ext']), \
        _insert_sys_path(root, lib_dir, build_dir):
      import distutils
      import distutils.core
      import distutils.command.build_ext

      # Tells distutils main() function to stop after parsing the command line,
      # but before actually trying to build stuff.
      distutils.core._setup_stop_after = "commandline"

      # Causes the actual 'build stuff' part to be a small explosion.
      class StopBeforeBuilding(Exception):
        pass
      def PreventBuild(*_):
        raise StopBeforeBuilding('boom')
      distutils.command.build_ext.build_ext.build_extensions = PreventBuild
      distutils.command.build_ext.build_ext.build_extension = PreventBuild

      # Have cpython's setup function actually invoke distutils to do
      # everything.
      import setup
      setup.main()

    # We stopped before running any commands. We then pull the 'build_ext'
    # command out of the distribution (which core nicely caches for us at
    # distutils.core), and then finish finalizing it and then 'run' it.
    ext_builder = (
        distutils.core._setup_distribution.get_command_obj('build_ext'))
    ext_builder.ensure_finalized()

    # This does a bunch of additional setup (like setting Command.compiler), and
    # then ultimately invokes setup.PyBuildExt.build_extensions(). This function
    # analyzes the current Modules/Setup.local, and then saves an Extension for
    # every module which should be dynamically built.
    #
    # It then calls through to the base `build_extensions` function, which we
    # earlier stubbed to raise an exception, and then finally prints some
    # summary information to stdout. Since we don't care to see the extra info
    # on # stdout, we catch the exception, then look at the .extensions member.
    try:
      ext_builder.run()
    except StopBeforeBuilding:
      pass

    # Finally, we get all the extensions which should be built for this
    # platform!
    for ext in ext_builder.extensions:
      assert isinstance(ext, distutils.extension.Extension)
      # some extensions are special and doesn't get fully configured until it's
      # actually built. *sigh*
      try:
        ext_builder.build_extension(ext)
      except StopBeforeBuilding:
        pass
  return ext_builder.extensions


def _escape(v):
  v = v.replace(r'"', r'\\"')
  return v


def _root_abspath(root, root_macro, v):
  if os.path.isabs(v):
    return v

  # Try appending root to the source name.
  av = os.path.join(root, v)
  if not os.path.isfile(av):
    # When sources other than "Modules/**" are referenced, the path does not
    # include the "Modules/" prefix.
    if os.path.join(root, 'Modules', v):
      return os.path.join(root_macro, 'Modules', v)

  # The Modules version doesn't exist, so this could be a to-be-created path.
  return os.path.join(root_macro, v)

def _define_macro(d):
  k, v = map(str, d)
  if not v:
    return '-D%s' % (k,)

  # Escape quotes in "v", since this will appear in a Makefile we have to
  # double-escape it.
  return "'-D%s=%s'" % (k, _escape(str(v)))


def _flag_dirs(root, root_macro, flag, dirs):
  for d in dirs:
    d = _root_abspath(root, root_macro, d)
    yield '-%s%s' % (flag, d)


def _replace_suffix(root, root_macro, l, old_suffix, new_suffix):
  for v in l:
    if v.endswith(old_suffix):
      v = v[:-len(old_suffix)] + new_suffix
    yield _root_abspath(root, root_macro, v)


def main(argv):
  def _arg_abspath(v):
    return os.path.abspath(v)

  def _arg_mod_augmentation(v):
    parts = v.split('::', 1)
    if len(parts) == 1:
      return (None, v)
    return parts

  parser = argparse.ArgumentParser()
  parser.add_argument('--root', required=True, type=_arg_abspath,
      help='Path to the root of the Python checkout, containing "setup.py".')
  parser.add_argument('--output', required=True, type=_arg_abspath,
      help='Path to the output Setup file.')
  parser.add_argument('--skip', default=[], action='append',
      help='Name of a Python module to skip when translating.')
  parser.add_argument('--attach',
      action='append', default=[], type=_arg_mod_augmentation,
      help='Series of [MOD::]VALUE pairs of text to attach to the end of a '
           'given module definition. If no MOD is supplied, VALUE will be '
           'attached to all lines.')
  args = parser.parse_args(argv)
  args.skip = set(args.skip)

  # We need to clear the existing "Setup.local", as it can influence module
  # probing.
  setup_local_path = os.path.join(args.root, 'Modules', 'Setup.local')
  log('Clearing existing Setup.local: %r', setup_local_path)
  with open(setup_local_path, 'w+') as fd:
    pass

  build_dir = os.path.join(args.root, get_build_dir(args.root))
  log('Using build directory: %r', build_dir)

  log('Loading base extension definitions...')
  os.chdir(args.root)
  exts = _get_extensions(args.root, build_dir)

  # Compile our attachments into a dict.
  attachments = {}
  for mod, app in args.attach:
    attachments.setdefault(mod, []).append(app)

  # Generate our output file with this information.
  with open(args.output, 'w') as fd:
    def w(line):
      fd.write(line)
      fd.write('\n')

    # Use this macro to make things more human-readable.
    root_macro_name = 'srcroot'
    root_macro = '$(%s)' % (root_macro_name,)

    # Include a banner.
    w('# This file was AUTO-GENERATED by Chrome Operations.')
    w('# Its contents are derived from the extension script defined in')
    w('# "setup.py" by processing it and extracting its extension definitions.')
    w('# The results are then fed back through "setup.py" with a header ')
    w('# telling it to compile them statically.')
    w('')
    w('*static*')
    w('')
    w('%s=%s' % (root_macro_name, args.root))

    # While it's more correct to have every module line list the static
    # libraries that we need to link against, Python will blindly aggregate
    # them in its linking command, duplicates and all, resulting a pretty
    # horrendous command. Avoid this by only emitting static library
    # dependencies once and relying on Python's "Setup.local" parsing and
    # integration to properly propagate these to the actual linking command.
    common_macros = [
        ('MOD_COMMON_ATTACH', attachments.get(None, ())),
    ]

    for ext in exts:
      if ext.name in args.skip:
        log('Skipping module: %r', ext.name)
        continue

      log('Emitting module: %r', ext.name)

      # Define statements don't parse properly if they have equals signs in
      # them. Rather than care about this too much, we'll just define a special
      # Makefile variable for each module with the defined values in it.
      macros = []
      def add_macro(base, v):
        v = v or ()
        name = 'MOD_%s__%s' % (base, ext.name)
        macros.append((name, v))

      add_macro('DEFINES', [_define_macro(d) for d in ext.define_macros])
      add_macro('INCLUDES',
          _flag_dirs(args.root, root_macro, 'I', ext.include_dirs))
      add_macro('EXTRA_COMPILE', ext.extra_compile_args)
      add_macro('EXTRA_LINK', ext.extra_link_args)
      add_macro('ATTACHMENTS', attachments.get(ext.name))

      # First time, emit common macros.
      if common_macros:
        macros += common_macros
        common_macros = None

      entry = [
          ext.name,
      ]
      entry += [_root_abspath(args.root, root_macro, s) for s in ext.sources]
      entry += _replace_suffix(
          args.root, root_macro, ext.extra_objects or (), '.o', '.c')
      entry += _flag_dirs(args.root, root_macro, 'L', ext.library_dirs)
      for name, ents in macros:
        if not ents:
          continue
        w('%s=%s' % (name, ' '.join(ents)))
        entry.append('$(%s)' % (name,))

      w(' '.join(entry))
      w('')


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
