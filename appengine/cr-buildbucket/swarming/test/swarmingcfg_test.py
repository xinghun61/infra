
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
      builder_defaults=Swarming.Builder(
        swarming_tags=['master:master.a'],
        dimensions=['cores:8', 'pool:default', 'cpu:x86-64'],
      ),
      builders=[
        Swarming.Builder(
          name='release',
          swarming_tags=['a:b'],
          dimensions=['os:Linux', 'cpu:'],
          caches=[Swarming.Builder.CacheEntry(
              name='git_chromium',
              path='git_cache',
          )],
          cipd_packages=[Swarming.Builder.CipdPackage(
            package_name='infra/test',
            path='third_party',
            version='latest',
          )],
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
        hostname='chromium-swarm.appspot.com',
        builders=[Swarming.Builder()],
    )
    self.cfg_test(cfg, [
      'builder #1: name unspecified',
      'builder #1: has no "pool" dimension',
      'builder #1: recipe: name unspecified',
      'builder #1: recipe: repository unspecified',
    ])

    cfg = Swarming(
        hostname='chromium-swarm.appspot.com',
        builder_defaults=Swarming.Builder(name='x'),
    )
    self.cfg_test(cfg, [
      'builder_defaults: do not specify default name',
    ])

    cfg = Swarming(
      task_template_canary_percentage=102,
      builder_defaults=Swarming.Builder(
          swarming_tags=['wrong'],
          dimensions=[''],
      ),
      builders=[
        Swarming.Builder(
          swarming_tags=['wrong2'],
          dimensions=[':', 'a.b:c', 'pool:default'],
        ),
        Swarming.Builder(
          name='b2',
          swarming_tags=['builder:b2'],
          dimensions=['x:y', 'x:y2'],
          cipd_packages=[
            Swarming.Builder.CipdPackage(
              package_name='',
              path='/',
              version='::',
            ),
            Swarming.Builder.CipdPackage(
              package_name='$name',
              path='\\path',
              version='VER_1',
            )
          ],
          caches=[
            Swarming.Builder.CacheEntry(),
            Swarming.Builder.CacheEntry(name='a/b', path='a'),
          ],
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
          priority=300,
        ),
      ],
    )
    self.cfg_test(cfg, [
      'hostname unspecified',
      'task_template_canary_percentage must must be in [0, 100]',
      'builder_defaults: tag #1: does not have ":": wrong',
      'builder_defaults: dimension #1: does not have ":"',
      'builder #1: tag #1: does not have ":": wrong2',
      'builder #1: dimension #1: no key',
      ('builder #1: dimension #2: '
       'key "a.b" does not match pattern "^[a-zA-Z\_\-]+$"'),
      ('builder b2: tag #1: do not specify builder tag; '
       'it is added by swarmbucket automatically'),
      'builder b2: dimension #2: duplicate key x',
      ('builder b2: cipd_package #1: '
       'package_name must be a valid CIPD package name template'),
      'builder b2: cipd_package #1: path cannot start with "/"',
      ('builder b2: cipd_package #1: '
       'version must be a valid CIPD package version'),
      ('builder b2: cipd_package #2: '
       'package_name must be a valid CIPD package name template'),
      ('builder b2: cipd_package #2: path cannot contain \\. '
       'On Windows forward-slashes will be replaced with back-slashes.'),
      ('builder b2: cipd_package #2: '
       'version must be a valid CIPD package version'),
      'builder b2: cache #1: name is required',
      'builder b2: cache #1: path is required',
      'builder b2: cache #2: name "a/b" does not match ^[a-z0-9_]{1,4096}$',
      'builder b2: recipe: properties #1: does not have colon',
      'builder b2: recipe: properties #2: key not specified',
      ('builder b2: recipe: properties #3: '
       'do not specify buildername property; '
       'it is added by swarmbucket automatically'),
      'builder b2: recipe: properties_j #1: duplicate property "x"',
      'builder b2: recipe: properties_j #2: No JSON object could be decoded',
      'builder b2: recipe: properties_j #3: does not have colon',
      'builder b2: priority must be in [0, 200] range; got 300',
    ])

    cfg = Swarming(
      task_template_canary_percentage=102,
      builder_defaults=Swarming.Builder(
        swarming_tags=['wrong'],
        dimensions=[''],
      ),
      builders=[
        Swarming.Builder(
            swarming_tags=['wrong2'],
            dimensions=[':', 'a.b:c', 'pool:default'],
        ),
        Swarming.Builder(
            name='b2',
            swarming_tags=['builder:b2'],
            dimensions=['x:y', 'x:y2'],
            cipd_packages=[
              Swarming.Builder.CipdPackage(
                package_name='${foo}',
              ),
              Swarming.Builder.CipdPackage(
                package_name='${platform}',
                path='..',
                version='$ref',
              ),
            ],
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
            priority=300,
        ),
      ],
    )
    self.cfg_test(cfg, [
      'hostname unspecified',
      'task_template_canary_percentage must must be in [0, 100]',
      'builder_defaults: tag #1: does not have ":": wrong',
      'builder_defaults: dimension #1: does not have ":"',
      'builder #1: tag #1: does not have ":": wrong2',
      'builder #1: dimension #1: no key',
      ('builder #1: dimension #2: '
       'key "a.b" does not match pattern "^[a-zA-Z\_\-]+$"'),
      ('builder b2: tag #1: do not specify builder tag; '
       'it is added by swarmbucket automatically'),
      'builder b2: dimension #2: duplicate key x',
      ('builder b2: cipd_package #1: '
       'package_name must be a valid CIPD package name template'),
      'builder b2: cipd_package #1: path is required',
      ('builder b2: cipd_package #1: '
       'version must be a valid CIPD package version'),
      'builder b2: cipd_package #2: path cannot contain ".."',
      ('builder b2: cipd_package #2: '
       'version must be a valid CIPD package version'),
      'builder b2: recipe: properties #1: does not have colon',
      'builder b2: recipe: properties #2: key not specified',
      ('builder b2: recipe: properties #3: '
       'do not specify buildername property; '
       'it is added by swarmbucket automatically'),
      'builder b2: recipe: properties_j #1: duplicate property "x"',
      'builder b2: recipe: properties_j #2: No JSON object could be decoded',
      'builder b2: recipe: properties_j #3: does not have colon',
      'builder b2: priority must be in [0, 200] range; got 300',
    ])


  def test_default_recipe(self):
    cfg = Swarming(
      hostname='chromium-swarm.appspot.com',
      builder_defaults=Swarming.Builder(
        dimensions=['pool:default'],
        recipe=Swarming.Recipe(
          repository='https://x.com',
          name='foo',
          properties=['a:b', 'x:y'],
        ),
      ),
      builders=[
        Swarming.Builder(name='debug'),
        Swarming.Builder(
          name='release',
          recipe=Swarming.Recipe(
            properties=['a:c'],
            properties_j=['x:null']),
        ),
      ],
    )
    self.cfg_test(cfg, [])

  def test_default_recipe_bad(self):
    cfg = Swarming(
        hostname='chromium-swarm.appspot.com',
        builder_defaults=Swarming.Builder(
          dimensions=['pool:default'],
          recipe=Swarming.Recipe(
              name='foo',
              properties=['a'],
          ),
        ),
        builders=[
          Swarming.Builder(name='debug'),
        ],
    )
    self.cfg_test(cfg, [
      'builder_defaults: recipe: properties #1: does not have colon',
    ])
