#!/usr/bin/python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Read DEPS and use the information to update git submodules"""

# CAUTION: this module has been cloned to a new version under
# infra/libs, with the expectation that callers of this original
# version will be migrated to use the new version (and eventually
# remove this old version).
#
# TODO(crbug/834373): do so.

import argparse
import collections
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile


SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')
SHA1_REF_RE = re.compile(r'^([0-9a-fA-F]{40})\s+refs/[\w/]+\s*')


def SanitizeDeps(submods, path_prefix, disable_path_prefix=False):
  """
  Look for conflicts (primarily nested submodules) in submodule data.  In the
  case of a conflict, the higher-level (shallower) submodule takes precedence.
  Modifies the submods argument in-place. If disable_path_prefix is True,
  won't check or strip submodule prefix.
  """
  ret = {}
  for name, value in submods.iteritems():
    # Strip trailing slashes, which git update-index can't handle.
    name = name.rstrip('/')

    if not disable_path_prefix and not name.startswith(path_prefix):
      # Won't check prefix if disabled path_prefix
      logging.warning('Dropping submodule "%s", because it is outside the '
                      'working directory "%s"', name, path_prefix)
      continue

    prefix = path_prefix
    if disable_path_prefix:
      prefix = name.split('/')[0] + '/'
    # Strip the prefix from the submodule name.
    name_strip_prefix = name[len(prefix):]
    if not disable_path_prefix:
      # If enable path_prefix, submodule name should be stripped prefix
      name = name_strip_prefix

    parts = name_strip_prefix.split('/')[:-1]
    while parts:
      may_conflict = prefix + '/'.join(parts)
      if may_conflict in submods:
        logging.warning('Dropping submodule "%s", because it is nested in '
                        'submodule "%s"', name, may_conflict)
        break
      parts.pop()
    else:
      ret[name] = value
  return ret


def AddExtraSubmodules(deps, extra_submodules):
  """
  Adds extra submodules to the list of deps.

  extra_submodules is a list of 'path=url' strings, where path is relative to
  the parent directory, and url is the URL of a git repository.
  """
  for extra_submodule in extra_submodules:
    path, url = extra_submodule.split('=', 2)

    sha1 = ResolveRef(url, 'refs/heads/master')
    if sha1 is None:
      continue

    deps[path] = {'url': url, 'rev': sha1}

  return deps


def ResolveRef(url, ref):
  """
  Queries a remote git repository at url for the sha1 hash of the given ref.
  """
  if ref.startswith('origin/'):
    ref = ref[7:]

  output = subprocess.check_output(['git', 'ls-remote', url, ref])
  match = SHA1_REF_RE.match(output)
  if not match:
    logging.warning('Could not resolve ref %s for %s', ref, url)
    return None
  sha1 = match.group(1)
  logging.info('Resolved %s for %s to %s', ref, url, sha1)
  return sha1


def WriteGitmodules(submods):
  """
  Take the submodules info, use it to write a .gitmodules file and
  return a map of submodule name -> sha1 to be added to the git index.
  """
  adds = collections.OrderedDict()
  with open('.gitmodules', 'w') as fh:
    for name, value in sorted(submods.iteritems()):
      url = value['url']
      sha1 = value['rev']

      if url.startswith('svn://'):
        logging.warning('Skipping svn url %s', url)
        continue

      print >> fh, '[submodule "%s"]' % name
      print >> fh, '\tpath = %s' % name
      print >> fh, '\turl = %s' % url

      if not sha1:
        sha1 = 'master'

      # Resolve the ref to a sha1 hash.
      if not SHA1_RE.match(sha1):
        sha1 = ResolveRef(url, sha1)
        if sha1 is None:
          continue

      logging.info('Added submodule %s revision %s', name, sha1)
      adds.pop(name, None)
      adds[name] = sha1
  subprocess.check_call(['git', 'add', '.gitmodules'])
  return adds


def RemoveObsoleteSubmodules():
  """
  Delete from the git repository any submodules which aren't in .gitmodules.
  """
  lsfiles = subprocess.check_output(['git', 'ls-files', '-s'])
  for line in lsfiles.splitlines():
    if not line.startswith('160000'):
      continue
    _, _, _, path = line.split()

    cmd = ['git', 'config', '-f', '.gitmodules',
           '--get-regexp', 'submodule\..*\.path', '^%s$' % path]
    try:
      with open(os.devnull, 'w') as nullpipe:
        subprocess.check_call(cmd, stdout=nullpipe)
    except subprocess.CalledProcessError:
      subprocess.check_call(['git', 'update-index', '--force-remove', path])


def main():
  logging.basicConfig(level=logging.INFO)
  parser = argparse.ArgumentParser()
  parser.add_argument('--path-prefix',
                      default=os.path.basename(os.getcwd()) + '/',
                      help='Ignore any dep outside this prefix. DEPS files can '
                      "specify dependencies in the repo's parent directory, "
                      'so the default here is to ignore anything outside the '
                      "current directory's basename")
  parser.add_argument('--disable-path-prefix', action='store_true',
                      default=False, help=argparse.SUPPRESS)
  parser.add_argument('--extra-submodule',
                      action='append', default=[],
                      help='path and URL of an extra submodule to add, '
                      'separated by an equals sign')
  parser.add_argument('revinfo_file', default='revinfo', nargs='?')
  options = parser.parse_args()

  if not options.path_prefix.endswith('/'):
    parser.error("--path-prefix '%s' must end with a '/'" % options.path_prefix)

  deps = json.load(open(options.revinfo_file, 'rU'))
  extra_deps = AddExtraSubmodules(deps, options.extra_submodule)
  deps.update(extra_deps)
  deps = SanitizeDeps(deps, options.path_prefix, options.disable_path_prefix)

  adds = WriteGitmodules(deps)
  RemoveObsoleteSubmodules()
  for submod_path, submod_sha1 in adds.iteritems():
    subprocess.check_call(['git', 'update-index', '--add',
                           '--cacheinfo', '160000', submod_sha1, submod_path])
  return 0


if __name__ == '__main__':
  sys.exit(main())
