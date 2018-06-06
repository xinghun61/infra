#!/usr/bin/python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for formatting and writing DEPS files."""


def ExpandVars(local_scope, vars_dict):
  """Expand the variables in |local_scope| using |vars_dict|.

  It does so by running 's.format(**vars_dict)' for all strings |s| in the
  |local_scope| dictionary.
  """
  def _visit(node):
    if isinstance(node, dict):
      return {
          _visit(k): _visit(v)
          for k, v in node.iteritems()
      }
    if isinstance(node, list) or isinstance(node, tuple):
      return [_visit(e) for e in node]
    if isinstance(node, basestring):
      return node.format(**vars_dict)
    return node
  return _visit(local_scope)


def GetDepsContent(deps_content):
  """Return all the sections of a DEPS file content."""
  local_scope = {}
  global_scope = {
      # gclient supports two ways to reference a variable:
      # Var('foo') and '{foo}', and we define Var to make them equivalent.
      # Note that to assign values to the variables, we can use the format
      # function:
      #   '{foo}/bar.git'.format({'foo': 'val'}) == 'val/bar.git'
      'Var': lambda x: '{%s}' % x,
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
  local_scope = {
    'deps': local_scope.get('deps', {}),
    'deps_os': local_scope.get('deps_os', {}),
    'include_rules': local_scope.get('include_rules', []),
    'skip_child_includes': local_scope.get('skip_child_includes', []),
    'hooks': local_scope.get('hooks', []),
    'vars': local_scope.get('vars', {}),
    'recursedeps': local_scope.get('recursedeps', []),
    'use_relative_paths': local_scope.get('use_relative_paths', False),
  }
  return ExpandVars(local_scope, local_scope['vars'])
