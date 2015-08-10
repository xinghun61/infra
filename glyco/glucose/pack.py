# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import hashlib
import os
import shutil
import sys
import textwrap

from glucose import util
from glucose import zipfix


def grab_wheel(src, dst, build_num=0):
  """Move a single wheel file and fix its name.

  Args:
    src (str): directory containing one wheel file.
    dst (str): directory where to put the renamed wheel file.

  Returns:
     wheel_filename (str): path to the generated file, in its final location.
  """
  items = os.listdir(src)
  assert len(items) == 1, (
    'Wrong number of files (%r) in wheel directory: %r' % (items, src))

  wheelfile = items[0]
  wheel_info = util.WHEEL_FILE_RE.match(wheelfile)

  assert wheel_info is not None, (
    'Not a wheel file? %r' % os.path.join(src, wheelfile))

  src_path = os.path.join(src, wheelfile)
  zipfix.reset_all_timestamps_in_zip(src_path)

  plat_tag = ''
  if not wheelfile.endswith('none-any.whl'):
    plat_tag = util.platform_tag()

  with open(src_path, 'rb') as f:
    digest = hashlib.sha1(f.read())
  wheel_sha = digest.hexdigest()

  dest_path = os.path.join(dst, '{}-{}_{}{}{}'.format(
      wheel_info.group('namever'),
      build_num,
      wheel_sha,
      plat_tag,
      wheel_info.group(4),
  ))
  shutil.copyfile(src_path, dest_path)
  return dest_path


def get_packing_list(source_dirs):
  """Consolidate the list of things to pack.

  Args:
    source_dirs (list of str): local source packages locations.
  """
  packing_list = []
  for source_dir in source_dirs:
    location = util.path2fileurl(os.path.abspath(source_dir))
    if os.path.isfile(os.path.join(source_dir, 'setup.py')):
      package_type = 'standard'
    elif (os.path.isfile(os.path.join(source_dir, 'setup.cfg')) and
          os.path.isfile(os.path.join(source_dir, '__init__.py'))):
      package_type = 'bare'
    else:
      package_type = 'unhandled'
      if not os.path.exists(source_dir):
        package_type = 'missing'
    packing_list.append({'location': location, 'package_type': package_type})
  return packing_list


def get_setup_py_content(cfg_path):
  """Generate a setup.py file based on a setup.cfg file.

  The setup.cfg file is supposed to live within the package itself: the
  name of the directory containing setup.cfg is treated as the package name.

  Args:
    cfg_path (str): path to a setup.cfg file.

  Returns:
    content (str): content of setup.py.
  """
  parser = ConfigParser.ConfigParser()
  parser.read(cfg_path)

  if not parser.has_section('metadata'):
    raise util.SetupError('Config file must have a [metadata] section: %s' %
                          cfg_path)

  package_name = os.path.split(os.path.dirname(cfg_path))[-1]
  setup_kwargs = {'name': package_name, 'packages': [package_name]}

  section = 'metadata'
  for option in ('version', 'author', 'author_email', 'description', 'url'):
    if parser.has_option(section, option):
      setup_kwargs[option] = parser.get(section, option)

  if parser.has_option('metadata', 'package_data'):
    setup_kwargs['package_data'] = parser.get('metadata',
                                              'package_data').splitlines()

  setup_py_template = textwrap.dedent("""
  from setuptools import setup

  setup(
    {keywords}
  )
  """)
  keywords = ['%s=%r' % (k, v) for k, v in sorted(setup_kwargs.iteritems())]
  return setup_py_template.format(keywords=',\n  '.join(keywords))


def pack_local_package(venv, path, wheelhouse, build_num=0, build_options=()):
  """Create a wheel file from package source available locally.

  Args:
    path (str): directory containing the package to pack.
    wheelhouse (str): directory where to place the generated wheel file.
    build_num (int): rank of the build, only added to the filename.
    build_options (list of str): values passed as --global-option to pip.

  Returns:
    wheel_path (str): path to the generated wheel file.
  """
  print 'Packing %s' % path
  with util.temporary_directory() as tempdir:
    args = ['pip', 'wheel', '--no-index', '--no-deps', '--wheel-dir', tempdir]
    for op in build_options:
      args += ['--global-option', op]
    args += [path]
    venv.check_call(args)
    wheel_path = grab_wheel(tempdir, wheelhouse, build_num)
  return wheel_path


def pack_bare_package(venv, path, wheelhouse, build_num=0, build_options=(),
                      keep_directory=False):
  """Create a wheel file from an importable package containing a setup.cfg file.

  Args:
    path (str): directory containing the package to pack.
    wheelhouse (str): directory where to place the generated wheel file.
    build_num (int): rank of the build, only added to the filename.
    build_options (list of str): values passed as --global-option to pip.

  Returns:
    wheel_path (str): path to the generated wheel file.
  """
  path = os.path.abspath(path)

  print 'Packing %s' % path

  # Generate a "standard" package with a setup.py file, and call
  # pack_local_package()
  cfg_file = os.path.join(path, 'setup.cfg')
  setup_py_content = get_setup_py_content(cfg_file)
  package_name = os.path.split(path)[-1]

  with util.temporary_directory(prefix="glyco-pack-bare-",
                                keep_directory=keep_directory) as tempdir:
    if keep_directory:
      print '  Using temporary dir: %s' % tempdir
    with open(os.path.join(tempdir, 'setup.py'), 'w') as f:
      f.write(setup_py_content)

    shutil.copytree(path, os.path.join(tempdir, package_name), symlinks=True)

    wheel_path = pack_local_package(venv, tempdir,
                                    wheelhouse,
                                    build_num=build_num,
                                    build_options=build_options)
  return wheel_path


def pack(args):
  """Pack wheel files.

  Returns 0 or None if all went well, a non-zero int otherwise.
  """

  if not args.packages:
    print 'No packages have been provided on the command-line, doing nothing.'
    return 0

  packing_list = get_packing_list(args.packages)

  unhandled = [util.fileurl2path(d['location'])
               for d in packing_list
               if d['package_type'] in ('unhandled', 'missing')]
  if unhandled:
    print >> sys.stderr, ('These directories do not seem to be packable '
                          'because they do not exist or\n'
                          'have neither setup.cfg or setup.py inside them:')
    print >> sys.stderr, ('\n'.join(unhandled))
    return 1


  if not os.path.isdir(args.output_dir):
    os.mkdir(args.output_dir)

  wheel_paths = []
  with util.Virtualenv(
      prefix="glyco-pack-",
      keep_directory=args.keep_tmp_directories) as venv:
    for element in packing_list:
      if element['location'].startswith('file://'):
        pathname = util.fileurl2path(element['location'])

        # Standard Python source package: contains a setup.py
        if element['package_type'] == 'standard':
          wheel_path = pack_local_package(venv, pathname, args.output_dir)

        # The Glyco special case: importable package with a setup.cfg file.
        elif element['package_type'] == 'bare':
          wheel_path = pack_bare_package(
            venv,
            pathname,
            args.output_dir,
            keep_directory=args.keep_tmp_directories)

        wheel_paths.append(wheel_path)

    if args.verbose:
      print '\nGenerated %d packages:' % len(wheel_paths)
      for wheel_path in wheel_paths:
        print wheel_path


def add_subparser(subparsers):
  """Add the 'pack' command.

  Also add the 'gen' command as a synonym.

  Args:
    subparsers: output of argparse.ArgumentParser.add_subparsers()
  """
  pack_parser = subparsers.add_parser('pack',
                                      help='Compile wheel files from Python '
                                      'packages (synonym of gen).')
  pack_parser.set_defaults(command=pack)

  # Add synonym, just for the pun
  gen_parser = subparsers.add_parser('gen',
                                     help='Compile wheel files from Python '
                                     'packages (synonym of pack).')
  gen_parser.set_defaults(command=pack)

  for parser in (pack_parser, gen_parser):
    parser.add_argument('--output-dir', '-o',
                        help='Directory where to write generated wheel files. '
                        'Default: %(default)s',
                        default='glyco_wheels')

    parser.add_argument('packages', metavar='PKG_PATH', nargs='*',
                        help='Local directory containing Python packages'
                        ' to process. These directories are supposed to contain'
                        ' a setup.py or a setup.cfg file.')
