# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_test_api

import json

class RecipeTryjobTestApi(recipe_test_api.RecipeTestApi):
  def make_recipe_config(self, name, deps=()):
    # TODO(iannucci): replace with self.m.json.dumps
    return json.dumps({
      'api_version': 2,
      'project_id': name,
      'recipes_path': '',
      'deps': {
        dep: {
          'url': 'https://repo.example.com/%s.git' % dep,
          'branch': 'master',
          'revision': 'deadbeef',
        } for dep in deps
      },
    }, sort_keys=True)
