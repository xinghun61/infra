# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.config import ConfigGroup, Single


DEPS = [
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/platform',
]


PROPERTIES = {
    '$infra/infra_system': Property(
      param_name='properties',
      help='Properties specifically for the the infra infra_system path '
           'module.',
      kind=ConfigGroup(
        # The absolute path to the temporary directory that the recipe should
        # use.
        sys_bin_dir=Single(str),
      ), default={},
    )
}
