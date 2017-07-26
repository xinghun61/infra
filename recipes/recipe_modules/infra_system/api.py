# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib

from recipe_engine import recipe_api


class InfraSystemApi(recipe_api.RecipeApi):
  """API for interacting with a provisioned infrastructure system."""

  def __init__(self, properties, **kwargs):
    super(InfraSystemApi, self).__init__(**kwargs)
    self._properties = properties

  @property
  def sys_bin_path(self):
    return self._properties.get('sys_bin_path', (
        'C:\\infra-system\\bin' if self.m.platform.is_win
        else '/opt/infra-system/bin'))

  @contextlib.contextmanager
  def system_env(self):
    """Yields a context modified to operate on system paths."""
    sys_bin_path = self.sys_bin_path
    self.m.path.mock_add_paths(sys_bin_path)
    assert self.m.path.exists(sys_bin_path), (
        'System binary path does not exist: %r' % (sys_bin_path,))

    with self.m.context(env_prefixes={'PATH': [sys_bin_path]}):
      yield
