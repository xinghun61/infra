
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import config as config_component
from testing_utils import testing

from proto import project_config_pb2
from test import config_test
from swarming import swarmingcfg


Swarming = project_config_pb2.Swarming


class SwarmingCfgTest(testing.AppengineTestCase):
  def test_validate_config(self):
    def test(cfg, expected_errors):
      ctx = config_component.validation.Context()
      swarmingcfg.validate_cfg(cfg, ctx)
      self.assertEqual(
        map(config_test.errmsg, expected_errors),
        ctx.result().messages)

    cfg = Swarming(
      hostname='chromium-swam.appspot.com',
      common_swarming_tags=['master:master.a'],
      common_dimensions=[Swarming.Dimension(key='cores', value='8')],
      builders=[
        Swarming.Builder(
          name='release',
          swarming_tags=['builder:release'],
          dimensions=[Swarming.Dimension(key='os', value='Linux')],
          recipe=Swarming.Recipe(
            repository='https://x.com',
            name='foo')
        ),
      ],
    )
    test(cfg, [])

    test(Swarming(), ['hostname unspecified'])

    cfg = Swarming(
      common_swarming_tags=['wrong'],
      common_dimensions=[Swarming.Dimension()],
      builders=[
        Swarming.Builder(
          swarming_tags=['wrong2'],
          dimensions=[Swarming.Dimension()],
        ),
        Swarming.Builder(
          name='b2',
          recipe=Swarming.Recipe(),
          priority=-1,
        ),
      ],
    )
    test(cfg, [
      'hostname unspecified',
      'common tag #1: does not have ":": wrong',
      'common dimension #1: no key',
      'common dimension #1: no value',
      'builder #1: name unspecified',
      'builder #1: tag #1: does not have ":": wrong2',
      'builder #1: dimension #1: no key',
      'builder #1: dimension #1: no value',
      'builder #1: recipe unspecified',
      'builder b2: recipe: name unspecified',
      'builder b2: recipe: repository unspecified',
      'builder b2: priority must be in [0, 200] range; got -1',
    ])
