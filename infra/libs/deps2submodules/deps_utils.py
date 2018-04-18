# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for access to dependency information in DEPS files.

This is a temporary clone of code from the deps2submodules resource of
the sync_submodules recipe module.  It should soon be replaced with
code allowing shared access to gclient_eval.
"""
# TODO(crbug/818798): replace this with refactored access to gclient_eval

class VarImpl(object):
  """Implement the Var function used within the DEPS file."""

  def __init__(self, local_scope):
    self._local_scope = local_scope

  def Lookup(self, var_name):
    """Implements the Var syntax."""
    if var_name in self._local_scope.get('vars', {}):
      return self._local_scope['vars'][var_name]
    raise Exception('Var is not defined: %s' % var_name)


def EvalDepsContent(deps_content):
  """Return all the sections of a DEPS file content."""
  local_scope = {}
  var = VarImpl(local_scope)
  global_scope = {
      'Var': var.Lookup,
      'deps': {},
      'deps_os': {},
      'include_rules': [],
      'skip_child_includes': [],
      'hooks': [],
      'vars': {},
      'recursedeps': [],
      'use_relative_paths': False,
  }
  exec(deps_content, global_scope, local_scope)
  return {
      'deps': local_scope.get('deps', {}),
      'deps_os': local_scope.get('deps_os', {}),
      'include_rules': local_scope.get('include_rules', []),
      'skip_child_includes': local_scope.get('skip_child_includes', []),
      'hooks': local_scope.get('hooks', []),
      'vars': local_scope.get('vars', {}),
      'recursedeps': local_scope.get('recursedeps', []),
      'use_relative_paths': local_scope.get('use_relative_paths', False),
  }


def ExtractUrl(dep):
  """Extracts the URL from a DEPS entry.

  Args:
    dep: the value from one entry in a `deps` or `deps_os` dict entry of a DEPS
        file.  It may be either a string (simply the URL itself), or a dict
        with a 'url' key.

  Returns:
    The URL, or None to indicate that it should be excluded from processing.
  """
  # The dep is either simply a URL, or a dictionary containing various fields
  # usually including (but not limited to) a URL and a conditional flag.
  # The submodule should be excluded (filtered out) if a condition is present
  # that says so, or if it can't be referred to by git URL in the first place.
  if isinstance(dep, basestring):
    return dep
  if not isinstance(dep, dict):
    raise TypeError('Dependency is neither a string nor a dict: %s' % dep)
  url = dep['url']  # deliberate KeyError if missing
  condition = dep.get('condition', '')
  # TODO(crbug/808599): replace this error-prone hack with something more
  # sensible/robust.  Due to rollback of crrev/c/899672, agable@ explains
  # that an expedient solution such as this is needed.
  filtered = condition.find('checkout_google_internal') >= 0
  return None if filtered else url
