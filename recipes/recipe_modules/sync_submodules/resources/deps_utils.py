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


def GetDepsContent(deps_path):
  """Read a DEPS file and return all the sections."""
  with open(deps_path, 'rU') as fh:
    content = fh.read()
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
  }
  exec(content, global_scope, local_scope)
  local_scope.setdefault('deps', {})
  local_scope.setdefault('deps_os', {})
  local_scope.setdefault('include_rules', [])
  local_scope.setdefault('skip_child_includes', [])
  local_scope.setdefault('hooks', [])
  local_scope.setdefault('vars', {})
  local_scope.setdefault('recursedeps', [])

  return (local_scope['deps'], local_scope['deps_os'],
          local_scope['include_rules'], local_scope['skip_child_includes'],
          local_scope['hooks'], local_scope['vars'], local_scope['recursedeps'])
