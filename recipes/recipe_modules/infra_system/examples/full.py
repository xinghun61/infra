# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'infra_system',
    'recipe_engine/context',
    'recipe_engine/platform',
    'recipe_engine/step',
]


def RunSteps(api):
  with api.infra_system.system_env():
    api.step('dump env', ['echo'])


def GenTests(api):
  for plat in ('linux', 'mac', 'win'):
    yield (
        api.test(plat) +
        api.platform(plat, 64))
