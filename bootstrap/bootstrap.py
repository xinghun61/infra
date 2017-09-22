#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from util import STORAGE_URL, OBJECT_URL, LOCAL_STORAGE_PATH, LOCAL_OBJECT_URL
from util import build_manifest, filter_deps, read_python_literal, \
                 merge_deps, print_deps, platform_tag

LOGGER = logging.getLogger(__name__)

# /path/to/infra
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PYTHON_BAT_WIN = '@%~dp0\\..\\Scripts\\python.exe %*'


class NoWheelException(Exception):
  def __init__(self, name, version, build, source_sha):
    super(NoWheelException, self).__init__(
        'No matching wheel found for (%s==%s (build %s_%s))' %
        (name, version, build, source_sha))


def check_pydistutils():
  if os.path.exists(os.path.expanduser('~/.pydistutils.cfg')):
    print >> sys.stderr, '\n'.join([
      '',
      '',
      '=========== ERROR ===========',
      'You have a ~/.pydistutils.cfg file, which interferes with the ',
      'infra virtualenv environment. Please move it to the side and bootstrap ',
      'again. Once infra has bootstrapped, you may move it back.',
      '',
      'Upstream bug: https://github.com/pypa/virtualenv/issues/88/',
      ''
    ])
    sys.exit(1)


def ls(prefix):
  from pip._vendor import requests  # pylint: disable=E0611
  for retry in range(4):
    try:
      r = requests.get(STORAGE_URL, params=dict(
          prefix=prefix,
          fields='items(name,md5Hash)'
      ))
      r.raise_for_status()
      data = r.json()
      break
    except (requests.exceptions.SSLError, requests.exceptions.HTTPError) as ex:
      delay = 4 ** (retry-1)
      print >> sys.stderr, (
        "caught an error: %s: retrying in %f sec" % (ex, delay))
      time.sleep(delay)
      continue
  else:
    raise Exception("exceeded allowed retries!")
  entries = data.get('items', [])
  for entry in entries:
    entry['md5Hash'] = entry['md5Hash'].decode('base64').encode('hex')
    entry['local'] = False
    entry['link'] = OBJECT_URL.format(entry['name'], entry['md5Hash'])
  # Also look in the local cache
  entries.extend([
    {
      'name': fname,
      'md5Hash': None,
      'local': True,
      'link': LOCAL_OBJECT_URL.format(fname),
    }
    for fname in glob.glob(os.path.join(LOCAL_STORAGE_PATH,
                                        prefix.split('/')[-1] + '*'))])
  return entries


def sha_for(deps_entry):
  if 'rev' in deps_entry:
    return deps_entry['rev']
  else:
    return deps_entry['gs'].split('.')[0]


def get_links(deps):
  import pip.wheel  # pylint: disable=E0611
  plat_tag = platform_tag()  # this is something like '_Ubuntu_14.04' or ''

  links = []

  for name, dep in deps.iteritems():
    version, source_sha = dep['version'] , sha_for(dep)
    prefix = '{}-{}-{}_{}'.format(name, version, dep['build'], source_sha)

    generic_wheels = []
    platform_wheels = []
    local_wheels = []

    for entry in ls('wheels/'+prefix):
      fname = entry['name'].split('/')[-1]
      wheel_info = pip.wheel.Wheel.wheel_file_re.match(fname)
      if not wheel_info:
        LOGGER.warning('Skipping invalid wheel: %r', fname)
        continue

      # This check skips all obviously unsupported wheels (like Linux wheels on
      # Windows).
      if not pip.wheel.Wheel(fname).supported():
        continue

      if entry['local']:
        # A locally built wheel?
        local_wheels.append(entry)
      elif plat_tag and fname.startswith(prefix + plat_tag):
        # A wheel targeting our very specific platform (if any)? This is hit on
        # different versions of Ubuntu for example.
        platform_wheels.append(entry)
      else:
        # Some more generic wheel (e.g. 'linux1many' or source wheel).
        generic_wheels.append(entry)

    # Prefer local wheels if have them, then per-platform, then generic.
    wheel_set = local_wheels or platform_wheels or generic_wheels
    if not wheel_set:
      raise NoWheelException(name, version, dep['build'], source_sha)

    if len(wheel_set) != 1:
      LOGGER.warning('Letting pip choose a wheel for "%s":', name)
      for entry in wheel_set:
        LOGGER.warning(' * %s', entry['name'])

    links.extend(entry['link'] for entry in wheel_set)

  return links


@contextlib.contextmanager
def html_index(links):
  tf = tempfile.mktemp('.html')
  try:
    with open(tf, 'w') as f:
      print >> f, '<html><body>'
      for link in links:
        print >> f, '<a href="%s">wat</a>' % link
      print >> f, '</body></html>'
    yield tf
  finally:
    os.unlink(tf)


def install(deps):
  if sys.platform.startswith('win'):
    # On Windows, "pip" is installed as a standalone binary called "pip.exe".
    pip = [os.path.join(sys.prefix, 'Scripts', 'pip')]
  else:
    # On Linux, "pip" is a "#!/...python"-bootstrapped wrapper. Because of
    # shebang length limitations, we will manually run this through the
    # Python interpreter rather than relying on shebang interpretation.
    pip = [
        os.path.join(sys.prefix, 'bin', 'python'),
        os.path.join(sys.prefix, 'bin', 'pip'),
    ]

  links = get_links(deps)
  with html_index(links) as ipath:
    requirements = []
    # TODO(iannucci): Do this as a requirements.txt
    for name, deps_entry in deps.iteritems():
      if not deps_entry.get('implicit'):
        requirements.append('%s==%s' % (name, deps_entry['version']))
    subprocess.check_call(
        pip + ['install', '--no-index', '-f', ipath] + requirements)


def activate_env(env, manifest, quiet=False, run_within_virtualenv=False):
  if hasattr(sys, 'real_prefix'):
    if not run_within_virtualenv:
      LOGGER.error('Already activated environment!')
      return
    LOGGER.info('Discarding current VirtualEnv (--run-within-virtualenv)')
    sys.prefix = sys.real_prefix

  if not quiet:
    print 'Activating environment: %r' % env
  assert isinstance(manifest, dict)

  manifest_path = os.path.join(env, 'manifest.pyl')
  cur_manifest = read_python_literal(manifest_path)
  if cur_manifest != manifest:
    if not quiet:
      print '  Removing old environment: %r' % cur_manifest
    shutil.rmtree(env, ignore_errors=True)
    cur_manifest = None

  if cur_manifest is None:
    check_pydistutils()

    if not quiet:
      print '  Building new environment'
    # Add in bundled virtualenv lib
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'virtualenv'))
    import virtualenv  # pylint: disable=F0401
    virtualenv.create_environment(
        env, search_dirs=virtualenv.file_search_dirs())

  if not quiet:
    print '  Activating environment'
  # Ensure hermeticity during activation.
  os.environ.pop('PYTHONPATH', None)
  bin_dir = 'Scripts' if sys.platform.startswith('win') else 'bin'
  activate_this = os.path.join(env, bin_dir, 'activate_this.py')
  execfile(activate_this, dict(__file__=activate_this))

  if cur_manifest is None:
    deps = manifest['deps']
    if not quiet:
      print '  Installing deps'
      print_deps(deps, indent=2, with_implicit=False)
    install(deps)
    virtualenv.make_environment_relocatable(env)

    # Write the original deps (including metadata) as manifest.
    with open(manifest_path, 'wb') as f:
      f.write(repr(manifest) + '\n')

  # Create bin\python.bat on Windows to unify path where Python is found.
  if sys.platform.startswith('win'):
    bin_path = os.path.join(env, 'bin')
    if not os.path.isdir(bin_path):
      os.makedirs(bin_path)
    python_bat_path = os.path.join(bin_path, 'python.bat')
    if not os.path.isfile(python_bat_path):
      with open(python_bat_path, 'w') as python_bat_file:
        python_bat_file.write(PYTHON_BAT_WIN)

  if not quiet:
    print 'Done creating environment'


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('--deps-file', '--deps_file', action='append',
                      help='Path to deps.pyl file (may be used multiple times, '
                      'default: bootstrap/deps.pyl)')
  parser.add_argument('-q', '--quiet', action='store_true', default=False,
                      help='Supress all output')
  parser.add_argument('-r', '--run-within-virtualenv', action='store_true',
                      help='Run even if the script is being run within a '
                           'VirtualEnv.')
  parser.add_argument('env_path',
                      help='Path to place environment (default: %(default)s)',
                      default='ENV')
  opts = parser.parse_args(args)
  opts.deps_file = opts.deps_file or [os.path.join(ROOT, 'bootstrap/deps.pyl')]

  # Skip deps not available for this flavor of Python interpreter.
  #
  # Possible platform names:
  #   macosx_x86_64
  #   linux_i686
  #   linux_x86_64
  #   windows_i686
  #   windows_x86_64
  if sys.platform.startswith('linux'):
    osname = 'linux'
  elif sys.platform == 'darwin':
    osname = 'macosx'
  elif sys.platform == 'win32':
    osname = 'windows'
  else:
    osname = sys.platform
  if sys.maxsize == (2 ** 31) - 1:
    bitness = 'i686'
  else:
    bitness = 'x86_64'
  plat = '%s_%s' % (osname, bitness)

  deps, kicked = filter_deps(merge_deps(opts.deps_file), plat)
  manifest = build_manifest(deps)
  activate_env(opts.env_path, manifest, opts.quiet, opts.run_within_virtualenv)

  if not opts.quiet and kicked:
    print '---------------------------'
    print 'WARNING! WARNING! WARNING! '
    print '---------------------------'
    print 'The following deps were skipped, they are not available on %s' % plat
    for pkg, dep in sorted(kicked.iteritems()):
      print '  * %s (%s)' % (pkg, dep['version'])


if __name__ == '__main__':
  logging.basicConfig()
  LOGGER.setLevel(logging.DEBUG)
  sys.exit(main(sys.argv[1:]))
