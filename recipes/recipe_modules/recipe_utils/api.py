# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from recipe_engine import recipe_api

def get_deps(project_config):
  """ Get the recipe engine deps of a project from its recipes.cfg file. """
  # "[0]" Since parsing makes every field a list.
  return [dep['project_id'][0] for dep in project_config.get('deps', [])]

class RecipeUtilApi(recipe_api.RecipeApi):
  """
  This is intended as a utility module for recipes which are concerned with the
  recipe universe.

  TODO(martiniss): move to the recipe engine once luci-config support lands.
  """
  def __init__(self, *args, **kwargs):
    super(RecipeUtilApi, self).__init__(*args, **kwargs)
    self._config_cache = {}

  def get_recipes_path(self, project_config):
    # Returns a tuple of the path components to traverse from the root of the
    # repo to get to the directory containing recipes.
    return project_config['recipes_path'][0].split('/')

  def get_deps_info(self, projects):
    """Calculates dependency information (forward and backwards).

    Forward means a mapping of package to what it depends on.
    Backwards means a mapping of package to what depends on it.
    Given:

        A
       / \
      B   C

    Forward would have B -> A, C -> A.
    Backwards would have A -> [B, C].
    """
    deps = {p: get_deps(self.get_project_config(p)) for p in projects}

    downstream_projects = collections.defaultdict(set)
    for proj, targets in deps.items():
      for target in targets:
        downstream_projects[target].add(proj)

    return deps, dict(downstream_projects)

  def get_project_config(self, project):
    """Fetch the project config from luci-config.

    Args:
      project: The name of the project in luci-config.

    Returns:
      The recipes.cfg file for that project, as a parsed dictionary. See
      parse_protobuf for details on the format to expect.
    """
    if not project in self._config_cache:
      result = self.m.luci_config.get_project_config(project, 'recipes.cfg')

      self._config_cache[project] = self.m.luci_config.parse_textproto(
          result['content'].split('\n'))

    return self._config_cache[project]


