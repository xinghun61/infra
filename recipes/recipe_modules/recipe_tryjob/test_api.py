# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_test_api


class RecipeTryjobTestApi(recipe_test_api.RecipeTestApi):
  def make_recipe_config(self, name, deps=None):
    if not deps:
      deps = []

    # Deps should be a list of project ids
    config = [
        'api_version: 1',
        'project_id: "%s"' % name,
        'recipes_path: ""',
    ]
    for dep in deps:
      config += [
        'deps {',
        '  project_id: "%s"' % dep,
        '  url: "https://repo.url/foo.git"',
        '  branch: "master"',
        '  revision: "deadbeef"',
        '}',
      ]
    return '\n'.join(config)
