# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is an incomplete implementation of a DEPS file parser.

Now only keys 'vars', 'deps', and 'deps_os' are taken care of.

TODO: support strict mode, 'target_os', 'target_os_only', 'use_relative_paths',
      both forms of recursion, both forms of hooks, 'allowed_hosts', etc.
"""

from common import dependency


# All supported OSes in DEPS file.
DEPS_OS_CHOICES = ('win', 'ios', 'mac', 'unix', 'android')


class DEPSLoader(object):
  def Load(self, repo_url, revision, deps_file):
    """Return the raw content of the DEPS file if it exists, otherwise None.

    Args:
      repo_url (str): the url to the repo of the dependency. Eg., for skia,
          it is https://chromium.googlesource.com/skia.git.
      revision (str): the revision of the dependency.
      deps_file (str): the path to the DEPS file in the dependency.
    """
    raise NotImplementedError()


class VarImpl(object):
  def __init__(self, local_scope):
    self._local_scope = local_scope

  def Lookup(self, var_name):
    if var_name not in self._local_scope.get('vars', {}):
      raise KeyError('Var is not defined: %s' % var_name)
    return self._local_scope['vars'][var_name]


def ParseDEPSContent(deps_content, keys=('deps', 'deps_os')):
  """Return dependencies by parsing the content of chromium DEPS file.

  Args:
    deps_content (str): the content of a DEPS file. It is assumed to be trusted
        and will be evaluated as python code.
    keys (iterable): optional, an iterable (list, tuple) of keys whose values
        needed to be returned in the order as the given keys. Each key is a str.
        Default keys are 'deps' and 'deps_os'.

  Returns:
    A list of values corresponding to and in the order as the given keys.

  Example usage::

    Content of the DEPS file "/tmp/DEPS" is as below:
      vars = {
          'aRevision': '123a',
          'bRevision': '234b'
      }
      deps = {
          'src/a': 'https://a.git' + '@' + Var('aRevision'),
          'src/b': 'https://b.git' + '@' + Var('bRevision'),
      }
      deps_os = {
          'unix': {
              'src/c': 'https://c.git@123c',
          }
      }

    Sample code:
      from infra.libs.deps import deps_parser
      with open('/tmp/DEPS', 'r') as f:
        deps_content = f.read()
      deps_os, deps = deps_parser.ParseDEPSContent(
          deps_content, keys=['deps_os', 'deps'])

    Then ``deps_os`` and ``deps`` above are dicts as below:
      deps_os = {
          'unix': {'src/c': 'https://c.git@123c'}
      }
      deps = {
          'src/a': 'https://a.git@123a',
          'src/b': 'https://b.git@123b'
      }
  """
  local_scope = {
      'vars': {},
      'allowed_hosts': [],
      'deps': {},
      'deps_os': {},
      'include_rules': [],
      'skip_child_includes': [],
      'hooks': [],
  }
  var = VarImpl(local_scope)
  global_scope = {
      'Var': var.Lookup,
      'vars': {},
      'allowed_hosts': [],
      'deps': {},
      'deps_os': {},
      'include_rules': [],
      'skip_child_includes': [],
      'hooks': [],
  }
  exec deps_content in global_scope, local_scope

  return [local_scope.get(key) for key in keys]


def MergeWithOsDeps(deps, deps_os, target_os_list):
  """Returns a new "deps" structure that is the deps sent in updated with
  information from deps_os (the deps_os section of the DEPS file) that matches
  the list of target os."""
  os_deps = {}

  def IsAllNoneForPath(path):
    # Check if the dependency identified by the given path is explicitly
    # specified as None in all OSes.
    for os in target_os_list:
      target_os_deps = deps_os.get(os, {})
      if path not in target_os_deps:
        return False
      elif target_os_deps[path] is not None:
        return False
    return True

  for os in target_os_list:
    target_os_deps = deps_os.get(os, {})
    for path, url in target_os_deps.iteritems():
      if url is None:
        if IsAllNoneForPath(path):
          os_deps[path] = None
      elif path not in os_deps:
        os_deps[path] = url
      elif os_deps[path] > url:
        # Conflicts: gclient.py sorts the url list to get the same result.
        os_deps[path] = url

  new_deps = deps.copy()
  new_deps.update(os_deps)
  return new_deps


def UpdateDependencyTree(root_dep, target_os_list, deps_loader):
  """Update the given dependency with its whole sub-dependency tree.

  Args:
    root_dep (dependency.Dependency): the root dependency.
    target_os_list (list): a list of str. Each string is a target OS and should
        be one of 'win', 'ios', 'mac', 'unix', 'android', or 'all'. If 'all',
        dependencies of all supported target OSes will be included.
    deps_loader (DEPSLoader): an instance of a DEPSLoader implementation.
  """
  def _NormalizeTargetOSName(target_os):
    os_name = target_os.lower()
    assert os_name in DEPS_OS_CHOICES, 'Target OS "%s" is invalid' % os_name
    return os_name

  if 'all' in target_os_list:
    target_os_list = DEPS_OS_CHOICES
  else:
    target_os_list = [_NormalizeTargetOSName(name) for name in target_os_list]

  deps_content = deps_loader.Load(
      root_dep.repo_url, root_dep.revision, root_dep.deps_file)
  deps, deps_os = ParseDEPSContent(deps_content, keys=('deps', 'deps_os'))

  all_deps = MergeWithOsDeps(deps, deps_os, target_os_list)

  def _CreateDependency(path, repo_info):
    if not path.endswith('/'):
      path = path + '/'

    repo_url = repo_info
    revision = None
    if '@' in repo_info:
      # The dependency is pinned to some revision.
      repo_url, revision = repo_info.split('@')

    return dependency.Dependency(
        path, repo_url, revision, root_dep.deps_file)

  for path, repo_info in all_deps.iteritems():
    if repo_info is None:
      # The dependency is not needed for all the target os.
      continue

    sub_dep = _CreateDependency(path, repo_info)
    sub_dep.SetParent(root_dep)

    # TODO: go into the next level of dependency if needed.
