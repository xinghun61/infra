#!/usr/bin/python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for formatting and writing DEPS files."""


class VarImpl(object):
  """Implement the Var function used within the DEPS file."""

  def __init__(self, local_scope):
    self._local_scope = local_scope

  def Lookup(self, var_name):
    """Implements the Var syntax."""
    if var_name in self._local_scope.get('vars', {}):
      return self._local_scope['vars'][var_name]
    raise Exception('Var is not defined: %s' % var_name)


def GetDepsContent(deps_content):
  """Return all the sections of a DEPSf file content."""
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
