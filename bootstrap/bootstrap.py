#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile

from util import STORAGE_URL, OBJECT_URL
from util import read_deps, merge_deps, print_deps, platform_tag

LOGGER = logging.getLogger(__name__)

# /path/to/infra
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoWheelException(Exception):
  def __init__(self, name, version, build, source_sha):
    super(NoWheelException, self).__init__(
        'No matching wheel found for (%s==%s (build %s_%s))' %
        (name, version, build, source_sha))


def ls(prefix):
  from pip._vendor import requests  # pylint: disable=E0611
  data = requests.get(STORAGE_URL, params=dict(
      prefix=prefix,
      fields='items(name,md5Hash)'
  )).json()
  return data.get('items', ())


def sha_for(deps_entry):
  if 'rev' in deps_entry:
    return deps_entry['rev']
  else:
    return deps_entry['gs'].split('.')[0]


def get_links(deps):
  import pip.wheel  # pylint: disable=E0611

  plat_tag = platform_tag()

  links = []

  for name, dep in deps.iteritems():
    version, source_sha = dep['version'] , sha_for(dep)
    prefix = 'wheels/{}-{}-{}_{}'.format(name, version, dep['build'],
                                         source_sha)
    generic_link = None
    binary_link = None

    for entry in ls(prefix):
      fname = entry['name'].split('/')[-1]
      md5hash = entry['md5Hash'].decode('base64').encode('hex')
      wheel_info = pip.wheel.Wheel.wheel_file_re.match(fname)
      if not wheel_info:
        LOGGER.warn('Skipping invalid wheel: %r', fname)
        continue

      if pip.wheel.Wheel(fname).supported():
        link = OBJECT_URL.format(entry['name'], md5hash)
        if fname.endswith('none-any.whl'):
          if generic_link:
            LOGGER.error(
              'Found more than one generic matching wheel for %r: %r',
              prefix, dep)
            continue
          generic_link = link
        elif plat_tag in fname:
          if binary_link:
            LOGGER.error(
              'Found more than one binary matching wheel for %r: %r',
              prefix, dep)
            continue
          binary_link = link

    if not binary_link and not generic_link:
      raise NoWheelException(name, version, dep['build'], source_sha)

    links.append(binary_link or generic_link)

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
  py = os.path.join(sys.prefix, 'bin', 'python')
  pip = os.path.join(sys.prefix, 'bin', 'pip')

  links = get_links(deps)
  with html_index(links) as ipath:
    requirements = []
    # TODO(iannucci): Do this as a requirements.txt
    for name, deps_entry in deps.iteritems():
      if not deps_entry.get('implicit'):
        requirements.append('%s==%s' % (name, deps_entry['version']))
    subprocess.check_call(
        [py, pip, 'install', '--no-index', '--download-cache',
         os.path.join(ROOT, '.wheelcache'), '-f', ipath] + requirements)


def activate_env(env, deps):
  if hasattr(sys, 'real_prefix'):
    LOGGER.error('Already activated environment!')
    return

  print 'Activating environment: %r' % env
  assert isinstance(deps, dict)

  manifest_path = os.path.join(env, 'manifest.pyl')
  cur_deps = read_deps(manifest_path)
  if cur_deps != deps:
    print '  Removing old environment: %r' % cur_deps
    shutil.rmtree(env, ignore_errors=True)
    cur_deps = None

  if cur_deps is None:
    print '  Building new environment'
    # Add in bundled virtualenv lib
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'virtualenv'))
    import virtualenv  # pylint: disable=F0401
    virtualenv.create_environment(
        env, search_dirs=virtualenv.file_search_dirs())

  print '  Activating environment'
  activate_this = os.path.join(env, 'bin', 'activate_this.py')
  execfile(activate_this, dict(__file__=activate_this))

  if cur_deps is None:
    print '  Installing deps'
    print_deps(deps, indent=2, with_implicit=False)
    install(deps)
    with open(manifest_path, 'wb') as f:
      f.write(repr(deps) + '\n')

  print 'Done creating environment'


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('--deps_file', action='append',
                      help='Path to deps.pyl file (may be used multiple times)')
  parser.add_argument('env_path',
                      help='Path to place environment (default: %(default)s)',
                      default='ENV')
  opts = parser.parse_args(args)

  deps = merge_deps(opts.deps_file)
  activate_env(opts.env_path, deps)


if __name__ == '__main__':
  logging.basicConfig()
  LOGGER.setLevel(logging.DEBUG)
  sys.exit(main(sys.argv[1:]))
