#!/usr/bin/python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Read DEPS and use the information to update git submodules"""

import argparse
import logging
import os
import re
import subprocess
import sys

from deps_utils import GetDepsContent


SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')
SHA1_REF_RE = re.compile(r'^([0-9a-fA-F]{40})\s+refs/[\w/]+\s*')


def SanitizeDeps(submods, path_prefix):
  """
  Look for conflicts (primarily nested submodules) in submodule data.  In the
  case of a conflict, the higher-level (shallower) submodule takes precedence.
  Modifies the submods argument in-place.
  """
  ret = {}
  for name, value in submods.iteritems():
    if not name.startswith(path_prefix):
      logging.warning('Dropping submodule "%s", because it is outside the '
                      'working directory "%s"', name, path_prefix)
      continue
    # Strip the prefix from the submodule name.
    name = name[len(path_prefix):]

    parts = name.split('/')[:-1]
    while parts:
      may_conflict = path_prefix + '/'.join(parts)
      if may_conflict in submods:
        logging.warning('Dropping submodule "%s", because it is nested in '
                        'submodule "%s"', name, may_conflict)
        break
      parts.pop()
    else:
      ret[name] = value
  return ret


def CollateDeps(deps_content):
  """
  Take the output of deps_utils.GetDepsContent and return a hash of:

  { submod_name : [ [ submod_os, ... ], submod_url, submod_sha1 ], ... }
  """
  spliturl = lambda x: list(x.partition('@')[0::2]) if x else [None, None]
  submods = {}
  # Non-OS-specific DEPS always override OS-specific deps. This is an interim
  # hack until there is a better way to handle OS-specific DEPS.
  for (deps_os, val) in deps_content[1].iteritems():
    for (dep, url) in val.iteritems():
      submod_data = submods.setdefault(dep, [[]] + spliturl(url))
      submod_data[0].append(deps_os)
  for (dep, url) in deps_content[0].iteritems():
    submods[dep] = [['all']] + spliturl(url)
  return submods


def WriteGitmodules(submods):
  """
  Take the output of CollateDeps, use it to write a .gitmodules file and
  return a map of submodule name -> sha1 to be added to the git index.
  """
  adds = {}
  with open('.gitmodules', 'w') as fh:
    for name, (os_name, url, sha1) in sorted(submods.iteritems()):
      if not url:
        continue

      if url.startswith('svn://'):
        logging.warning('Skipping svn url %s', url)
        continue

      print >> fh, '[submodule "%s"]' % name
      print >> fh, '\tpath = %s' % name
      print >> fh, '\turl = %s' % url
      print >> fh, '\tos = %s' % ','.join(os_name)

      if not sha1:
        sha1 = 'master'

      # Resolve the ref to a sha1 hash.
      if not SHA1_RE.match(sha1):
        if sha1.startswith('origin/'):
          sha1 = sha1[7:]

        output = subprocess.check_output(['git', 'ls-remote', url, sha1])
        match = SHA1_REF_RE.match(output)
        if not match:
          logging.warning('Could not resolve ref %s for %s', sha1, url)
          continue
        logging.info('Resolved %s for %s to %s', sha1, url, match.group(1))
        sha1 = match.group(1)

      logging.info('Added submodule %s revision %s', name, sha1)
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
  parser.add_argument('deps_file', default='DEPS', nargs='?')
  options = parser.parse_args()

  if not options.path_prefix.endswith('/'):
    parser.error("--path-prefix '%s' must end with a '/'" % options.path_prefix)

  adds = WriteGitmodules(
      SanitizeDeps(
          CollateDeps(GetDepsContent(options.deps_file)),
          options.path_prefix))
  RemoveObsoleteSubmodules()
  for submod_path, submod_sha1 in adds.iteritems():
    subprocess.check_call(['git', 'update-index', '--add',
                           '--cacheinfo', '160000', submod_sha1, submod_path])
  return 0


if __name__ == '__main__':
  sys.exit(main())
