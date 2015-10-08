# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import httplib2
import logging
import os
import sys
import urllib

from glucose import util


LOGGER = logging.getLogger(__name__)
DEFAULT_CACHE = os.path.join(os.path.expanduser('~'), '.glyco_wheelcache')


def get_sha1_from_filename(filename, verbose=True):
  """Extract the claimed sha1 from the filename.

  Also verify the name matches the wheel convention.

  Args:
    filename (str): path to a local file.
    verbose (bool): print messages only if True.

  Returns: claimed_hash(str) or None if no hash can be found.
  """

  basename = os.path.split(filename)[-1]
  wheel_info = util.WHEEL_FILE_RE.match(basename)
  if not wheel_info:
    if verbose:
      print >> sys.stderr, 'Invalid file name for wheel: %s' % basename
    return None

  if not wheel_info.group('build'):
    if verbose:
      print >> sys.stderr, ('No hash could be found in the filename.\n'
                            'Has this file been generated with Glyco?\n'
                            '%s' % basename)
    return None

  return wheel_info.group('build').split('_')[1]


def has_valid_sha1(filename, verbose=True):
  """Verify the hash of a whl file created by Glyco.

  Args:
    filename (str): path to a whl file.
    verbose(bool): print messages only if True.

  Returns:
    matches (bool): true if the file content and the name match.
  """
  claimed_sha = get_sha1_from_filename(filename, verbose=verbose)
  if not claimed_sha:
    return False

  with open(filename, 'rb') as f:
    digest = hashlib.sha1(f.read())
  actual_sha = digest.hexdigest()

  return actual_sha == claimed_sha


def get_install_list(packages):
  """Consolidate the list of things to install.

  Args:
    packages (list of str): local paths or https/gs URLs.
  """

  install_list = []
  for package in packages:
    location = package
    location_type = 'ERROR'
    error = None
    # Let's support only https. Security matters.
    if package.startswith('http://'):
      error = 'Non-secure http is not supported, please use https: %s' % package
    elif package.startswith('https://'):
      location_type = 'http'
    elif package.startswith('gs://'):
      # TODO(pgervais): handle Cloud Storage properly.
      location_type = 'http'
      location = 'https://storage.googleapis.com/' + package[len('gs://'):]
    elif os.path.isfile(package):
      location = 'file://%s' % urllib.pathname2url(os.path.abspath(package))
      location_type = 'file'
    else:
      error = ('Cannot find this file locally: %s\n'
                       'If you did not specify a file but an URI, '
                       'then the protocol is probably not supported.'
                       % os.path.abspath(package))

    install_list.append({'location': location,
                         'location_type': location_type,
                         'error': error})
  return install_list


def fetch_packages(install_list, requester=httplib2.Http(),
                   cache=DEFAULT_CACHE, verbose=True):
  """Make sure there is a local copy of all packages.

  All paths returned by this function point at existing wheel files, with
  correct hashes.

  Args:
    install_list (list of dict): return value of get_install_list.
    requester (httplib2.Http): object to use to send http requests.
    cache (str): path to a local directory used to store wheel files downloaded
      from a remote storage.
    verbose(bool): print messages only if True.

  Returns:
    paths (list of strings): path to each local wheel file.
  """

  if not os.path.isdir(cache):
    os.mkdir(cache)

  paths = []
  all_valid = True
  for source in install_list:
    if source['location_type'] == 'file':
      assert source['location'].startswith('file://')
      filename = source['location'][len('file://'):]
      # FIXME(pgervais): convert to a windows path (/ -> \) and unquote.
      if not has_valid_sha1(filename, verbose=verbose):
        if verbose:
          print >> sys.stderr, ("File content does not match hash for %s"
                                % filename)
        all_valid = False
      else:
        paths.append(filename)

    elif source['location_type'] == 'http':
      # This is an URL so the path separator is necessarily /
      base_filename = source['location'].split('/')[-1]
      filename = os.path.join(cache, base_filename)

      if not os.path.exists(filename):
        # Try to download file to local cache
        resp, content = requester.request(source['location'], 'GET')
        if resp['status'] == '200':
          temp_filename = os.path.join(cache, base_filename + '.tmp')
          try:
            with open(temp_filename, 'wb') as f:
              f.write(content)
            os.rename(temp_filename, filename)
          except OSError:
            if os.path.isfile(temp_filename):
              os.remove(temp_filename)
        else:
          if verbose:
            print >> sys.stderr, ("Got status %s when talking to %s" %
                                  (resp['status'], source['location']))
          all_valid = False

      # We have to test again for existence since the download
      # could have failed.
      if os.path.exists(filename) and not has_valid_sha1(filename,
                                                         verbose=verbose):
        if verbose:
          print >> sys.stderr, ("File content does not match hash for %s"
                                % filename)
        all_valid = False
        # The file is bad anyway, there's no point in keeping it around.
        # Plus we probably want to retry the download some time in the future.
        os.remove(filename)
      else:
        paths.append(filename)

  if not all_valid:
    raise ValueError('Some errors occurred when getting wheel files.')
  return paths


def install(args):
  """Install wheel files"""

  if not args.packages:
    print 'No packages have been provided on the command-line, doing nothing.'
    return

  if not args.install_dir:
    print >> sys.stderr, ('No destination directory specified, aborting. \n'
                          'Use the --install-dir option to specify it')
    return 2

  install_list = get_install_list(args.packages)
  error_msgs = [d['error'] for d in install_list if 'error' in d and d['error']]
  if error_msgs:
    print >> sys.stderr, ('\n'.join(error_msgs))
    print >> sys.stderr, 'Aborting (no packages installed)'
    return 1

  try:
    package_paths = fetch_packages(install_list)
  except ValueError:
    print >> sys.stderr, 'Aborting (no packages installed)'
    return 1

  if not os.path.isdir(args.install_dir):
    os.mkdir(args.install_dir)

  with util.Virtualenv() as venv:
    cmd = (['pip', 'install', '--no-deps', '--no-index', '--target',
            args.install_dir] + package_paths)
    LOGGER.debug('Running %s', ' '.join(cmd))
    venv.check_call(cmd)


def add_subparser(subparsers):
  """Add the 'install' command.

  Also add the 'lysis' command as a synonym (and pun).

  Args:
    subparsers: output of argparse.ArgumentParser.add_subparsers()
  """
  install_parser = subparsers.add_parser('install',
                                         help='Install wheel files to a local '
                                              'directory (synonym of lysis)')
  install_parser.set_defaults(command=install)

  # Add synonym just for the pun
  lysis_parser = subparsers.add_parser('lysis',
                                       help='Install wheel files to a local '
                                       'directory (synonym of install)')

  lysis_parser.set_defaults(command=install)

  for parser in (install_parser, lysis_parser):
    parser.add_argument('--install-dir', '-i',
                        help='Directory where to install packages')
    parser.add_argument('packages', metavar='PACKAGE', nargs='*',
                        help='Wheel files to install (path)')
