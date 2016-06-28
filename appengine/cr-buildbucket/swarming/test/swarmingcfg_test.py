
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
  def cfg_test(self, cfg, expected_errors):
    ctx = config_component.validation.Context()
    swarmingcfg.validate_cfg(cfg, ctx)
    self.assertEqual(
        map(config_test.errmsg, expected_errors),
        ctx.result().messages)

  def test_valid(self):
    cfg = Swarming(
      hostname='chromium-swarm.appspot.com',
      common_swarming_tags=['master:master.a'],
      common_dimensions=['cores:8', 'pool:default'],
      builders=[
        Swarming.Builder(
          name='release',
          swarming_tags=['a:b'],
          dimensions=['os:Linux'],
          recipe=Swarming.Recipe(
            repository='https://x.com',
            name='foo',
            properties=['a:b'],
            properties_j=['x:true'],
          ),
        ),
      ],
    )
    self.cfg_test(cfg, [])

  def test_empty(self):
    self.cfg_test(Swarming(), ['hostname unspecified'])

  def test_bad(self):
    cfg = Swarming(
      common_swarming_tags=['wrong'],
      common_dimensions=[''],
      builders=[
        Swarming.Builder(
          swarming_tags=['wrong2'],
          dimensions=[':', 'a.b:c', 'pool:default'],
        ),
        Swarming.Builder(
          name='b2',
          swarming_tags=['builder:b2'],
          dimensions=['x:y', 'x:y2'],
          recipe=Swarming.Recipe(
            properties=[
              '',
              ':',
              'buildername:foobar',
              'x:y',
            ],
            properties_j=[
              'x:"y"',
              'y:b',
              'z',
            ]
          ),
          priority=-1,
        ),
      ],
    )
    self.cfg_test(cfg, [
      'hostname unspecified',
      'common tag #1: does not have ":": wrong',
      'common dimension #1: does not have ":"',
      'builder #1: name unspecified',
      'builder #1: tag #1: does not have ":": wrong2',
      'builder #1: dimension #1: no key',
      'builder #1: dimension #1: no value',
      ('builder #1: dimension #2: '
       'key "a.b" does not match pattern "^[a-zA-Z\_\-]+$"'),
      'builder #1: recipe unspecified',
      ('builder b2: tag #1: do not specify builder tag; '
       'it is added by swarmbucket automatically'),
      'builder b2: dimension #2: duplicate key x',
      ('builder b2: has no "pool" dimension. '
       'Either define it in the builder or in "common_dimensions"'),
      'builder b2: recipe: name unspecified',
      'builder b2: recipe: repository unspecified',
      'builder b2: recipe: properties #1: does not have colon',
      'builder b2: recipe: properties #2: key not specified',
      ('builder b2: recipe: properties #3: '
       'do not specify buildername property; '
       'it is added by swarmbucket automatically'),
      'builder b2: recipe: properties_j #1: duplicate property "x"',
      'builder b2: recipe: properties_j #2: No JSON object could be decoded',
      'builder b2: recipe: properties_j #3: does not have colon',
      'builder b2: priority must be in [0, 200] range; got -1',
    ])

  def test_common_recipe(self):
    cfg = Swarming(
        hostname='chromium-swarm.appspot.com',
        common_dimensions=['pool:default'],
        common_recipe=Swarming.Recipe(
            repository='https://x.com',
            name='foo',
            properties=['a:b'],
        ),
        builders=[
          Swarming.Builder(name='debug'),
          Swarming.Builder(
              name='release',
              recipe=Swarming.Recipe(properties=['a:c']),
          ),
        ],
    )
    self.cfg_test(cfg, [])

  def test_common_recipe_bad(self):
    cfg = Swarming(
        hostname='chromium-swarm.appspot.com',
        common_dimensions=['pool:default'],
        common_recipe=Swarming.Recipe(
            name='foo',
            properties=['a'],
        ),
        builders=[
          Swarming.Builder(name='debug'),
        ],
    )
    self.cfg_test(cfg, [
      'common_recipe: properties #1: does not have colon',
      'builder debug: recipe: repository unspecified',
    ])
