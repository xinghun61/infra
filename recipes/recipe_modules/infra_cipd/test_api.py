# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_test_api
from recipe_engine.config_types import Path, NamedBasePath


class InfraCIPDTestApi(recipe_test_api.RecipeTestApi):
  def example_upload(self):
    return self.m.json.output({
      'succeeded': [
        {
          'info': {
            'instance_id': 'abcdefabcdef63ad814cd1dfffe2fcfc9f81299c',
            'package': 'infra/tools/some_tool/os-bitness',
          },
          'pkg_def_name': 'some_tool',
        },
      ],
      'failed': [],
    })
