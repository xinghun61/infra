
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import utils
utils.fix_protobuf_package()

from google import protobuf

from components import config as config_component
from testing_utils import testing

from proto import project_config_pb2
from test import config_test
from swarming import swarmingcfg


class SwarmingCfgTest(testing.AppengineTestCase):
  def cfg_test(self, cfg_text, expected_errors):
    ctx = config_component.validation.Context()
    cfg = project_config_pb2.Swarming()
    protobuf.text_format.Merge(cfg_text, cfg)
    swarmingcfg.validate_cfg(cfg, ctx)
    self.assertEqual(
        map(config_test.errmsg, expected_errors),
        ctx.result().messages)

  def test_valid(self):
    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builder_defaults {
            swarming_tags: "master:master.a"
            dimensions: "cores:8"
            dimensions: "pool:default"
            dimensions: "cpu:x86-64"
          }
          builders {
            name: "release"
            swarming_tags: "a:b'"
            dimensions: "os:Linux"
            dimensions: "cpu:"
            caches {
              name: "git_chromium"
              path: "git_cache"
            }
            recipe {
              repository: "https://x.com"
              name: "foo"
              properties: "a:b'"
              properties_j: "x:true"
            }
          }
        ''',
        [])

  def test_empty(self):
    self.cfg_test('', ['hostname unspecified'])

  def test_bad(self):
    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builders {}
        ''',
        [
          'builder #1: name unspecified',
          'builder #1: has no "pool" dimension',
          'builder #1: recipe: name unspecified',
          'builder #1: recipe: repository unspecified',
        ])

    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builder_defaults {name: "x"}
        ''',
        [
          'builder_defaults: do not specify default name',
        ])

    self.cfg_test(
        '''
          task_template_canary_percentage { value: 102 }
          builder_defaults {
            swarming_tags: "wrong"
            dimensions: ""
          }
          builders {
            swarming_tags: "wrong2"
            dimensions: ":"
            dimensions: "a.b:c"
            dimensions: "pool:default"
          }
          builders {
            name: "b2"
            swarming_tags: "builder:b2"
            dimensions: "x:y"
            dimensions: "x:y2"
            caches {}
            caches { name: "a/b" path: "a" }
            caches { name: "b" path: "a\\c" }
            caches { name: "c" path: "a/.." }
            caches { name: "d" path: "/a" }
            recipe {
              properties: ""
              properties: ":"
              properties: "buildername:foobar"
              properties: "x:y"
              properties_j: "x:\\\"y\\\""
              properties_j: "y:b"
              properties_j: "z"
            }
            priority: 300
          }
        ''',
        [
          'hostname unspecified',
          'task_template_canary_percentage.value must must be in [0, 100]',
          'builder_defaults: tag #1: does not have ":": wrong',
          'builder_defaults: dimension #1: does not have ":"',
          'builder #1: tag #1: does not have ":": wrong2',
          'builder #1: dimension #1: no key',
          ('builder #1: dimension #2: '
           'key "a.b" does not match pattern "^[a-zA-Z\_\-]+$"'),
          ('builder b2: tag #1: do not specify builder tag; '
           'it is added by swarmbucket automatically'),
          'builder b2: dimension #2: duplicate key x',
          'builder b2: cache #1: name is required',
          'builder b2: cache #1: path is required',
          'builder b2: cache #2: name "a/b" does not match ^[a-z0-9_]{1,4096}$',
          ('builder b2: cache #3: path cannot contain \\. '
           'On Windows forward-slashes will be replaced with back-slashes.'),
          'builder b2: cache #4: path cannot contain ".."',
          'builder b2: cache #5: path cannot start with "/"',
          'builder b2: recipe: properties #1: does not have colon',
          'builder b2: recipe: properties #2: key not specified',
          ('builder b2: recipe: properties #3: '
           'do not specify buildername property; '
           'it is added by swarmbucket automatically'),
          'builder b2: recipe: properties_j #1: duplicate property "x"',
          ('builder b2: recipe: properties_j #2: '
           'No JSON object could be decoded'),
          'builder b2: recipe: properties_j #3: does not have colon',
          'builder b2: priority must be in [0, 200] range; got 300',
        ])

    self.cfg_test(
        '''
          task_template_canary_percentage {value: 102}
          builder_defaults {
            swarming_tags: "wrong"
            dimensions: ""
          }
          builders {
            swarming_tags: "wrong2"
            dimensions: ":"
            dimensions: "a.b:c"
            dimensions: "pool:default"
          }
          builders {
            name: "b2"
            swarming_tags: "builder:b2"
            dimensions: "x:y"
            dimensions: "x:y2"
            recipe {
              properties: ""
              properties: ":"
              properties: "buildername:foobar"
              properties: "x:y"
              properties_j: "x:\\\"y\\\""
              properties_j: "y:b"
              properties_j: "z"
            }
            priority: 300
          }
        ''',
        [
          'hostname unspecified',
          'task_template_canary_percentage.value must must be in [0, 100]',
          'builder_defaults: tag #1: does not have ":": wrong',
          'builder_defaults: dimension #1: does not have ":"',
          'builder #1: tag #1: does not have ":": wrong2',
          'builder #1: dimension #1: no key',
          ('builder #1: dimension #2: '
           'key "a.b" does not match pattern "^[a-zA-Z\_\-]+$"'),
          ('builder b2: tag #1: do not specify builder tag; '
           'it is added by swarmbucket automatically'),
          'builder b2: dimension #2: duplicate key x',
          'builder b2: recipe: properties #1: does not have colon',
          'builder b2: recipe: properties #2: key not specified',
          ('builder b2: recipe: properties #3: '
           'do not specify buildername property; '
           'it is added by swarmbucket automatically'),
          'builder b2: recipe: properties_j #1: duplicate property "x"',
          ('builder b2: recipe: properties_j #2: '
           'No JSON object could be decoded'),
          'builder b2: recipe: properties_j #3: does not have colon',
          'builder b2: priority must be in [0, 200] range; got 300',
        ])

    self.cfg_test(
        '''
          hostname: "https://example.com"
          builders {
            name: "rel"
            caches { name: "a" path: "a" }
            caches { name: "a" path: "a" }
          }
        ''',
        [
          'builder rel: cache #2: duplicate name',
          'builder rel: cache #2: duplicate path',
        ])


  def test_default_recipe(self):
    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builder_defaults {
            dimensions: "pool:default"
            recipe {
              repository: "https://x.com"
              name: "foo"
              properties: "a:b"
              properties: "x:y"
           }
          }
          builders { name: "debug" }
          builders {
            name: "release"
            recipe {
              properties: "a:c"
              properties_j: "x:null"
            }
          }
        ''', [])

  def test_default_recipe_bad(self):
    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builder_defaults {
            dimensions: "pool:default"
            recipe {
                name: "foo"
                properties: "a"
            }
          }
          builders { name: "debug" }
        ''',
        [
          'builder_defaults: recipe: properties #1: does not have colon',
        ])
