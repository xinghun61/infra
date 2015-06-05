# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os
import shutil
import sys
import urllib

from glucose import util


def check_pydistutils():
  """Return True if a .pydistutils.cfg has been found."""
  if os.path.exists(os.path.expanduser('~/.pydistutils.cfg')):
    raise util.GlycoSetupError('\n'.join([
      '',
      'You have a ~/.pydistutils.cfg file, which interferes with the ',
      'infra virtualenv environment. Please move it to the side and bootstrap ',
      'again. Once infra has bootstrapped, you may move it back.',
      '',
      'Upstream bug: https://github.com/pypa/virtualenv/issues/88/',
      ''
    ]))


def setup_virtualenv(env_path, activate=False, relocatable=False):
  """Create a virtualenv in specified location.

  The virtualenv contains a standard Python installation, plus setuptools, pip
  and wheel.

  Args:
    env_path (str): where to create the virtual environment.
    activate (bool): if True, activate the virtualenv inside this process after
      creating it.
  """
  if hasattr(sys, 'real_prefix'):
    raise AssertionError('Environment already activated.')

  check_pydistutils()

  print 'Creating environment: %r' % env_path

  if os.path.exists(env_path):
    print '  Removing existing one...'
    shutil.rmtree(env_path, ignore_errors=True)


  print '  Building new environment...'
  # Import bundled virtualenv lib
  import virtualenv  # pylint: disable=F0401
  virtualenv.create_environment(
    env_path, search_dirs=virtualenv.file_search_dirs())

  if activate:
    print '  Activating environment'
    activate_virtualenv(env_path)

  if relocatable:
    print '  Make environment relocatable'
    virtualenv.make_environment_relocatable(env_path)

  print 'Done creating environment'


def activate_virtualenv(env_path):
  """Activate an existing virtualenv."""
  # Ensure hermeticity during activation.
  os.environ.pop('PYTHONPATH', None)
  bin_dir = 'Scripts' if sys.platform.startswith('win') else 'bin'
  activate_this = os.path.join(env_path, bin_dir, 'activate_this.py')
  execfile(activate_this, dict(__file__=activate_this))


def grab_wheel(src, dst, build_num=0):
  """Move a single wheel file and fix its name.

  Args:
    src (str): directory containing one wheel file.
    dst (str): directory where to put the renamed wheel file.

  Returns:
     wheel_filename (str): path to the generated file, in its final location.
  """
  # late import lets us grab the virtualenv pip
  from pip.wheel import Wheel  # pylint: disable=E0611

  items = os.listdir(src)
  assert len(items) == 1, (
    'Wrong number of files (%r) in wheel directory: %r' % (items, src))

  wheelfile = items[0]
  wheel_info = Wheel.wheel_file_re.match(wheelfile)

  assert wheel_info is not None, (
    'Not a wheel file? %r' % os.path.join(src, wheelfile))

  plat_tag = ''
  if not wheelfile.endswith('none-any.whl'):
    plat_tag = util.platform_tag()

  src_path = os.path.join(src, wheelfile)
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


def pack_local_package(path, wheelhouse, build_num=0, build_options=()):
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
  # run the appropriate pip command to generate a wheel file.
  with util.temporary_directory() as tempdir:
    args = ['wheel', '--no-index', '--no-deps', '--wheel-dir', tempdir]
    for op in build_options:
      args += ['--global-option', op]
    args += [path]
    util.pip(*args)
    grab_wheel(tempdir, wheelhouse, build_num)


def get_packing_list(source_dirs):
  """Consolidate the list of things to pack.

  Args:
    source_dirs (list of str): local source packages locations.
  """
  packing_list = []
  for source_dir in source_dirs:
    packing_list.append({'location': 'file://%s'
                         % urllib.pathname2url(os.path.abspath(source_dir))})
  return packing_list


def pack(args):
  """Pack wheel files."""

  if not args.source_dir:
    return

  packing_list = get_packing_list(args.source_dir)

  if not os.path.isdir(args.output_dir):
    os.makedirs(args.output_dir)

  with util.temporary_directory(
      prefix="glyco-pack-",
      keep_directory=args.keep_tmp_directories) as tempdir:
    setup_virtualenv(tempdir, activate=True)
    for element in packing_list:
      if element['location'].startswith('file://'):
        pack_local_package(urllib.url2pathname(element['location'][7:]),
                           args.output_dir)

  # Outside the with statement, the virtualenv directory has been deleted.
  # Virtualenvs cannot be deactivated from inside a Python interpreter, so we
  # have no choice but to exit asap.
  # TODO(pgervais): launch a separate process inside the virtualenv instead.
  sys.exit(0)


def add_subparser(subparsers):
  """Add the 'pack' command.

  Also add the 'gen' command as a synonym.

  Args:
    subparser: output of argparse.ArgumentParser.add_subparsers()
  """
  pack_parser = subparsers.add_parser('pack',
                                      help='Make wheel files from Python '
                                      'packages (synonym of gen).')
  pack_parser.set_defaults(command=pack)

  # Add synonym, just for the pun
  gen_parser = subparsers.add_parser('gen',
                                     help='Make wheel files from Python '
                                     'packages (synonym of pack).')
  gen_parser.set_defaults(command=pack)

  for parser in (pack_parser, gen_parser):
    parser.add_argument('--output-dir', '-o',
                        help='Directory where to write generated wheel files.',
                        default='glyco_wheels')

    parser.add_argument('--source-dir', '-s', nargs='*',
                        help='Local directory containing the Python package'
                        ' to process. This path contain a ./setup.py file.')
