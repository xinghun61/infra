
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import utils
utils.fix_protobuf_package()

from google import protobuf

from components import config as config_component
from testing_utils import testing

from proto import project_config_pb2
from proto import service_config_pb2
from test import config_test
from swarming import swarmingcfg


class ProjectCfgTest(testing.AppengineTestCase):
  def cfg_test(self, swarming_text, mixins_text, expected_errors):
    ctx = config_component.validation.Context()

    swarming_cfg = project_config_pb2.Swarming()
    protobuf.text_format.Merge(swarming_text, swarming_cfg)

    buildbucket_cfg = project_config_pb2.BuildbucketCfg()
    protobuf.text_format.Merge(mixins_text, buildbucket_cfg)

    mixins = {m.name: m for m in buildbucket_cfg.builder_mixins}
    swarmingcfg.validate_project_cfg(swarming_cfg, mixins, True, ctx)
    self.assertEqual(
        map(config_test.errmsg, expected_errors),
        ctx.result().messages)

  def test_valid(self):
    self.cfg_test(
        '''
          builder_defaults {
            swarming_tags: "master:master.a"
            dimensions: "cores:8"
            dimensions: "pool:default"
            dimensions: "cpu:x86-64"
            service_account: "bot"
          }
          builders {
            name: "release"
            swarming_tags: "a:b'"
            dimensions: "os:Linux"
            dimensions: "cpu:"
            service_account: "robot@example.com"
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
        '',
        [])

  def test_empty(self):
    self.cfg_test('', '', ['builders are not defined'])

  def test_bad(self):
    self.cfg_test(
        '''
          hostname: "chromium-swarm.appspot.com"
          builders {}
        ''',
        '',
        [
          'builder #1: name unspecified',
          'builder #1: has no "pool" dimension',
          'builder #1: recipe: name unspecified',
          'builder #1: recipe: repository unspecified',
        ])

    self.cfg_test(
        '''
          builder_defaults {name: "x"}
          builders {
            name: "release"
            dimensions: "pool:a"
            recipe {
              repository: "https://x.com"
              name: "foo"
            }
          }
        ''',
        '',
        [
          'builder_defaults: do not specify default name',
        ])

    self.cfg_test(
        '''
          hostname: "https://example.com"
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
        '',
        [
          'hostname: must not contain "://"',
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
        '',
        [
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
          hostname: "example.com"
          builders {
            name: "rel"
            caches { path: "a" name: "a" }
            caches { path: "a" name: "a" }
          }
        ''',
        '',
        [
          'builder rel: cache #2: duplicate name',
          'builder rel: cache #2: duplicate path',
        ])

    self.cfg_test(
        '''
          hostname: "example.com"
          builders {
            name: "b"
            service_account: "not an email"
          }
        ''',
        '',
        [
          'builder b: service_account: value "not an email" does not match '
          '^[0-9a-zA-Z_\\-\\.\\+\\%]+@[0-9a-zA-Z_\\-\\.]+$',
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
        ''', '', [])

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
        '',
        [
          'builder_defaults: recipe: properties #1: does not have colon',
        ])

  def test_validate_builder_mixins(self):
    def test(cfg_text, expected_errors):
      ctx = config_component.validation.Context()
      cfg = project_config_pb2.BuildbucketCfg()
      protobuf.text_format.Merge(cfg_text, cfg)
      swarmingcfg.validate_builder_mixins(cfg.builder_mixins, ctx)
      self.assertEqual(
          map(config_test.errmsg, expected_errors),
          ctx.result().messages)

    test(
        '''
          builder_mixins {
            name: "a"
            dimensions: "a:b"
          }
          builder_mixins {
            name: "b"
            mixins: "a"
            dimensions: "a:b"
          }
        ''',
        [])

    test(
        '''
          builder_mixins {
            name: "b"
            mixins: "a"
          }
          builder_mixins {
            name: "a"
          }
        ''',
        [])

    test(
        '''
          builder_mixins {}
        ''',
        [
          'builder_mixin #1: name unspecified'
        ])

    test(
        '''
          builder_mixins { name: "a" }
          builder_mixins { name: "a" }
        ''',
        [
          'builder_mixin a: duplicate name'
        ])

    test(
        '''
          builder_mixins {
            name: "a"
            mixins: ""
          }
        ''',
        [
          'builder_mixin a: referenced mixin name is empty'
        ])

    test(
        '''
          builder_mixins {
            name: "a"
            mixins: "b"
          }
        ''',
        [
          'builder_mixin a: mixin "b" is not defined'
        ])

    test(
        '''
          builder_mixins {
            name: "a"
            mixins: "a"
          }
        ''',
        [
          'circular mixin chain: a -> a',
        ])

    test(
        '''
          builder_mixins {
            name: "a"
            mixins: "b"
          }
          builder_mixins {
            name: "b"
            mixins: "c"
          }
          builder_mixins {
            name: "c"
            mixins: "a"
          }
        ''',
        [
          'circular mixin chain: a -> b -> c -> a',
        ])

  def test_builder_with_mixins(self):
    def test(cfg_text, expected_errors):
      ctx = config_component.validation.Context()
      cfg = project_config_pb2.BuildbucketCfg()
      protobuf.text_format.Merge(cfg_text, cfg)
      swarmingcfg.validate_builder_mixins(cfg.builder_mixins, ctx)
      self.assertEqual([], ctx.result().messages)
      mixins = {m.name: m for m in cfg.builder_mixins}
      swarmingcfg.validate_project_cfg(
          cfg.buckets[0].swarming, mixins, True, ctx)
      self.assertEqual(
          map(config_test.errmsg, expected_errors),
          ctx.result().messages)

    test(
        '''
          builder_mixins {
            name: "a"

            dimensions: "cores:8"
            dimensions: "cpu:x86-64"
            dimensions: "os:Linux"
            dimensions: "pool:default"
            caches {
              name: "git"
              path: "git"
            }
            recipe {
              repository: "https://x.com"
              name: "foo"
              properties: "a:b'"
              properties_j: "x:true"
            }
          }
          builder_mixins {
            name: "b"
            mixins: "a"
          }
          builder_mixins {
            name: "c"
            mixins: "a"
            mixins: "b"
          }
          buckets {
            name: "a"
            swarming {
              hostname: "chromium-swarm.appspot.com"
              builders {
                name: "release"
                mixins: "b"
                mixins: "c"
              }
            }
          }
        ''',
        []
    )

  def test_flatten_builder(self):
    def test(cfg_text, expected_builder_text):
      cfg = project_config_pb2.BuildbucketCfg()
      protobuf.text_format.Merge(cfg_text, cfg)
      builder = cfg.buckets[0].swarming.builders[0]
      swarmingcfg.flatten_builder(
          builder,
          cfg.buckets[0].swarming.builder_defaults,
          {m.name: m for m in cfg.builder_mixins},
      )

      expected = project_config_pb2.Builder()
      protobuf.text_format.Merge(expected_builder_text, expected)
      self.assertEqual(builder, expected)

    test(
      '''
        buckets {
          name: "bucket"
          swarming {
            hostname: "chromium-swarm.appspot.com"
            url_format: "https://example.com/{swarming_hostname}/{task_id}"
            builder_defaults {
              swarming_tags: "commontag:yes"
              dimensions: "cores:8"
              dimensions: "pool:default"
              dimensions: "cpu:x86-86"
              recipe {
                repository: "https://example.com/repo"
                name: "recipe"
              }
              caches {
                name: "git_chromium"
                path: "git_cache"
              }
              caches {
                name: "build_chromium"
                path: "out"
              }
            }
            builders {
              name: "builder"
              swarming_tags: "buildertag:yes"
              dimensions: "os:Linux"
              dimensions: "pool:Chrome"
              dimensions: "cpu:"
              priority: 108
              recipe {
                properties: "predefined-property:x"
                properties_j: "predefined-property-bool:true"
              }
              caches {
                name: "a"
                path: "a"
              }
            }
          }
        }
      ''',
      '''
        name: "builder"
        swarming_tags: "buildertag:yes"
        swarming_tags: "commontag:yes"
        dimensions: "cores:8"
        dimensions: "os:Linux"
        dimensions: "pool:Chrome"
        priority: 108
        recipe {
          repository: "https://example.com/repo"
          name: "recipe"
          properties_j: "predefined-property:\\\"x\\\""
          properties_j: "predefined-property-bool:true"
        }
        caches {
          name: "a"
          path: "a"
        }
        caches {
          name: "build_chromium"
          path: "out"
        }
        caches {
          name: "git_chromium"
          path: "git_cache"
        }
      '''
    )

    # Diamond merge.
    test(
        '''
          builder_mixins {
            name: "base"
            dimensions: "d1:base"
            dimensions: "d2:base"
            dimensions: "d3:base"
            swarming_tags: "t1:base"
            swarming_tags: "t2:base"
            swarming_tags: "t3:base"
            caches {
              name: "c1"
              path: "base"
            }
            caches {
              name: "c2"
              path: "base"
            }
            caches {
              name: "c3"
              path: "base"
            }
            recipe {
              name: "base"
              properties: "p1:base"
              properties: "p2:base"
              properties: "p3:base"
              properties_j: "pj1:\\\"base\\\""
              properties_j: "pj2:\\\"base\\\""
              properties_j: "pj3:\\\"base\\\""
            }
          }
          builder_mixins {
            name: "first"
            mixins: "base"
            dimensions: "d2:first"
            dimensions: "d3:first"
            swarming_tags: "t2:first"
            swarming_tags: "t3:first"
            caches {
              name: "c2"
              path: "first"
            }
            caches {
              name: "c3"
              path: "first"
            }
            recipe {
              repository: "https://example.com/first"
              name: "first"
              properties: "p2:first"
              properties_j: "pj2:\\\"first\\\""
            }
          }
          builder_mixins {
            name: "second"
            mixins: "base"
            dimensions: "d2:"
            dimensions: "d3:second"
            swarming_tags: "t3:second"
            caches {
              name: "c3"
              path: "second"
            }
            recipe {
              name: "second"
              properties: "p3:second"
              # Unset p2 and p2j
              properties_j: "p2:null"
              properties_j: "pj2:null"
              properties_j: "pj3:\\\"second\\\""
            }
          }
          buckets {
            name: "bucket"
            swarming {
              hostname: "chromium-swarm.appspot.com"
              builders {
                name: "builder"
                mixins: "first"
                mixins: "second"
              }
            }
          }
        ''',
        '''
          name: "builder"
          dimensions: "d1:base"
          dimensions: "d2:first"
          dimensions: "d3:second"
          swarming_tags: "t1:base"
          swarming_tags: "t2:base"
          swarming_tags: "t2:first"
          swarming_tags: "t3:base"
          swarming_tags: "t3:first"
          swarming_tags: "t3:second"
          caches {
            name: "c1"
            path: "base"
          }
          caches {
            name: "c2"
            path: "base"
          }
          caches {
            name: "c3"
            path: "second"
          }
          recipe {
            repository: "https://example.com/first"
            name: "second"
            properties_j: "p1:\\\"base\\\""
            properties_j: "p2:\\\"first\\\""
            properties_j: "p3:\\\"second\\\""
            properties_j: "pj1:\\\"base\\\""
            properties_j: "pj2:\\\"first\\\""
            properties_j: "pj3:\\\"second\\\""
          }
        '''
    )

    # builder_defaults, a builder_defaults mixin and a builder mixin.
    test(
        '''
          builder_mixins {
            name: "default"
            dimensions: "pool:builder_default_mixin"
          }
          builder_mixins {
            name: "builder"
            dimensions: "pool:builder_mixin"
          }
          buckets {
            name: "bucket"
            swarming {
              hostname: "chromium-swarm.appspot.com"
              builder_defaults {
                mixins: "default"
                dimensions: "pool:builder_defaults"
                recipe {
                  repository: "https://x.com"
                  name: "foo"
                }
              }
              builders {
                name: "release"
                mixins: "builder"
              }
            }
          }
        ''',
        '''
          name: "release"
          dimensions: "pool:builder_mixin"
          recipe {
            repository: "https://x.com"
            name: "foo"
          }
        ''')


class ServiceCfgTest(testing.AppengineTestCase):
  def cfg_test(self, swarming_text, expected_errors):
    ctx = config_component.validation.Context()

    settings = service_config_pb2.SwarmingSettings()
    protobuf.text_format.Merge(swarming_text, settings)

    swarmingcfg.validate_service_cfg(settings, ctx)
    self.assertEqual(
        map(config_test.errmsg, expected_errors),
        ctx.result().messages)

  def test_valid(self):
    self.cfg_test('default_hostname: "chromium-swarm.appspot.com"', [])

  def test_empty(self):
    self.cfg_test('', ['default_hostname: unspecified'])

  def test_schema_in_hostname(self):
    self.cfg_test(
        '''
          default_hostname: "https://swarming.example.com"
          milo_hostname: "https://milo.example.com"
        ''',
        [
          'default_hostname: must not contain "://"',
          'milo_hostname: must not contain "://"',
        ])
