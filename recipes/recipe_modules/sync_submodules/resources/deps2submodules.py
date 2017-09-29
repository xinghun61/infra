#!/usr/bin/python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Read DEPS and use the information to update git submodules"""

import argparse
import collections
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

from deps_utils import GetDepsContent


SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')
SHA1_REF_RE = re.compile(r'^([0-9a-fA-F]{40})\s+refs/[\w/]+\s*')


def SanitizeDeps(submods_list, path_prefix, disable_path_prefix=False):
  """
  Look for conflicts (primarily nested submodules) in submodule data.  In the
  case of a conflict, the higher-level (shallower) submodule takes precedence.
  Modifies the submods argument in-place. If disable_path_prefix is True,
  won't check or strip submodule prefix.
  """
  ret_list = []
  for submods in submods_list:
    ret = {}
    for name, value in submods.iteritems():
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
    ret_list.append(ret)
  return ret_list


def _AddPrefixToDepname(dep_name, prefix_path):
  """
  Some DEPS files enable 'use_relative_paths', which enables the names of 'deps'
  in those files relative to the directory. The dep_name should be relative to
  the source directory when convert to submodule name. This func fixes the
  relative dep_name path by adding a prefix path on it.
  """
  return os.path.normpath(os.path.join(prefix_path or ".", dep_name))


def _GetRecurseDepsDict(deps_content, submods, prefix_path="."):
  """
  Collect a dict of the recurse deps name, with recurse dep repo url and
  file name. Fix recurse deps name if deps_content using relative paths.

  Return: { dep_name : (repo_url, file_name), ... }
  """
  recursedeps = deps_content['recursedeps']
  recursedeps_path_dict = {} # { dep_name: (repo_url, file_name), ...}
  for dep in recursedeps:
    depname = dep
    depsfilename = 'DEPS'
    if isinstance(dep, tuple): # (depname, depsfilename)
      depname, depsfilename = dep
    if deps_content['use_relative_paths']:
      depname = _AddPrefixToDepname(depname, prefix_path)
    if depname in submods:
      repo_url = submods[depname][1]
      recursedeps_path_dict[depname] = (repo_url, depsfilename)
    else:
      logging.warning('Could not find repo url for recursedep %s', depname)

  return recursedeps_path_dict


def _CheckoutAndGetDepsContent(repo_url, file_name):
  """
  Check out git repo and get the deps file content. Take the output of
  deps_utils.GetDepsContent of the content.
  """
  checkout_dir = tempfile.mkdtemp()
  try:
    subprocess.check_call(['git', 'clone', '--depth=1', '--bare', repo_url,
                           checkout_dir])
    content = subprocess.check_output(['git', 'show', 'HEAD:%s' % file_name],
                                       cwd=checkout_dir)
    return GetDepsContent(content)
  finally:
    shutil.rmtree(checkout_dir)


def CollateCurrentDeps(deps_content, prefix_path="."):
  """
  Take the output of deps_utils.GetDepsContent and return a hash of:

  { submod_name : [ [ submod_os, ... ], submod_url, submod_sha1 ], ... }
  """
  spliturl = lambda x: list(x.partition('@')[0::2]) if x else [None, None]
  submods = {}
  # Non-OS-specific DEPS always override OS-specific deps. This is an interim
  # hack until there is a better way to handle OS-specific DEPS.
  for (deps_os, val) in deps_content['deps_os'].iteritems():
    for (dep, url) in val.iteritems():
      fix_dep_name = _AddPrefixToDepname(dep, prefix_path)
      # If DEP has conditional then we need to extract URL from dict.
      if isinstance(url, dict):
        url = url['url']
      submod_data = submods.setdefault(fix_dep_name, [[]] + spliturl(url))
      submod_data[0].append(deps_os)
  for (dep, url) in deps_content['deps'].iteritems():
    fix_dep_name = _AddPrefixToDepname(dep, prefix_path)
    # If DEP has conditional then we need to extract URL from dict.
    if isinstance(url, dict):
      url = url['url']
    submods[fix_dep_name] = [['all']] + spliturl(url)
  return submods


def CollateDeps(deps_file, enable_recurse_deps):
  """
  Collate submodules by taking the output of deps_utils.GetDepsContent for
  deps_file and its recurse deps files. If recurse deps are enabled, with
  breadth first going through each deps level, keep a dict of submodule
  hashes of one level, and return a list of those dict from highest deps
  level to lowest level:

  [
   { submod_name : [ [ submod_os, ... ], submod_url, submod_sha1 ], ... },
   { submod_name : [ [ submod_os, ... ], submod_url, submod_sha1 ], ... },
   ...
  ]
  """
  with open(deps_file, 'rU') as fh:
    deps_content = GetDepsContent(fh.read())
    submods = CollateCurrentDeps(deps_content)

  submods_list = []
  submods_list.append(submods)
  if not enable_recurse_deps:
    return submods_list

  recursedeps_dict = _GetRecurseDepsDict(deps_content, submods)
  while recursedeps_dict: # Breadth first going through each recurse deps level
    submods = {}
    next_recursedeps_dict = {}
    for dep_name, (repo_url, file_name) in recursedeps_dict.iteritems():
      recurse_deps_file_content = _CheckoutAndGetDepsContent(repo_url,
                                                             file_name)
      prefix = "."
      if recurse_deps_file_content['use_relative_paths']:
        prefix = dep_name
      submods.update(CollateCurrentDeps(recurse_deps_file_content, prefix))
      fix_next_recursedeps_dict = _GetRecurseDepsDict(
          recurse_deps_file_content, submods, dep_name)
      next_recursedeps_dict.update(fix_next_recursedeps_dict)
    recursedeps_dict = next_recursedeps_dict
    submods_list.append(submods)

  return submods_list


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

    deps[path] = (['all'], url, sha1)

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


def WriteGitmodules(submods_list):
  """
  Take the output of CollateDeps, use it to write a .gitmodules file and
  return a map of submodule name -> sha1 to be added to the git index.
  """
  adds = collections.OrderedDict()
  with open('.gitmodules', 'w') as fh:
    for submods in submods_list:
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
  parser.add_argument('deps_file', default='DEPS', nargs='?')
  parser.add_argument('--enable-recurse-deps', action='store_true',
                      default=False,
                      help='Enable collecting submodules for recursedeps.')
  options = parser.parse_args()

  if not options.path_prefix.endswith('/'):
    parser.error("--path-prefix '%s' must end with a '/'" % options.path_prefix)

  deps_list = CollateDeps(options.deps_file, options.enable_recurse_deps)
  extra_deps = AddExtraSubmodules(deps_list[0], options.extra_submodule)
  deps_list[0].update(extra_deps)
  deps_list = SanitizeDeps(deps_list, options.path_prefix,
                           options.disable_path_prefix)

  adds = WriteGitmodules(deps_list)
  RemoveObsoleteSubmodules()
  for submod_path, submod_sha1 in adds.iteritems():
    subprocess.check_call(['git', 'update-index', '--add',
                           '--cacheinfo', '160000', submod_sha1, submod_path])
  return 0


if __name__ == '__main__':
  sys.exit(main())
