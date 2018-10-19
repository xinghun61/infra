# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging

from parameterized import parameterized

from components import utils

utils.fix_protobuf_package()

from components import config as config_component
from components.config import validation_context
from google.protobuf import text_format
from testing_utils import testing
import mock

from proto.config import project_config_pb2
from swarming import flatten_swarmingcfg
import config
import errors

to_text = text_format.MessageToString
to_binary = lambda msg: msg.SerializeToString()


def parse_bucket_cfg(text):
  cfg = project_config_pb2.Bucket()
  text_format.Merge(text, cfg)
  return cfg


def short_bucket_cfg(cfg):
  cfg = copy.deepcopy(cfg)
  cfg.name = config.short_bucket_name(cfg.name)
  return cfg


LUCI_CHROMIUM_TRY = parse_bucket_cfg(
    '''name: "luci.chromium.try"
acls {
  group: "all"
}
swarming {
  builders {
    name: "linux"
    dimensions: "os:Linux"
    dimensions: "pool:luci.chromium.try"
    recipe {
      repository: "https://example.com"
      name: "x"
    }
  }
}
'''
)

LUCI_DART_TRY = parse_bucket_cfg(
    '''name: "luci.dart.try"
swarming {
  builders {
    name: "linux"
    dimensions: "pool:Dart.LUCI"
    recipe {
      repository: "https://example.com"
      name: "x"
    }
  }
}
'''
)

MASTER_TRYSERVER_CHROMIUM_LINUX = parse_bucket_cfg(
    '''name: "master.tryserver.chromium.linux"
acls {
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
'''
)

MASTER_TRYSERVER_CHROMIUM_WIN = parse_bucket_cfg(
    '''name: "master.tryserver.chromium.win"
acls {
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
'''
)

MASTER_TRYSERVER_CHROMIUM_MAC = parse_bucket_cfg(
    '''name: "master.tryserver.chromium.mac"
acls {
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
'''
)

MASTER_TRYSERVER_V8 = parse_bucket_cfg(
    '''name: "master.tryserver.v8"
acls {
  role: WRITER
  group: "v8-team"
}
'''
)

MASTER_TRYSERVER_TEST = parse_bucket_cfg(
    '''name: "master.tryserver.test"
acls {
  role: WRITER
  identity: "user:root@google.com"
}
'''
)


def parse_cfg(text):
  cfg = project_config_pb2.BuildbucketCfg()
  text_format.Merge(text, cfg)
  return cfg


def errmsg(text):
  return validation_context.Message(severity=logging.ERROR, text=text)


class ConfigTest(testing.AppengineTestCase):

  def test_get_bucket(self):
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    project_id, cfg = config.get_bucket('chromium/try')
    self.assertEqual(project_id, 'chromium')
    self.assertEqual(cfg, short_bucket_cfg(LUCI_CHROMIUM_TRY))

    self.assertIsNone(config.get_bucket('chromium/nonexistent')[0])

  def test_get_buckets_async(self):
    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_LINUX)
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    config.put_bucket('dart', 'deadbeef', LUCI_DART_TRY)
    actual = config.get_buckets_async().get_result()
    expected = {
        'chromium/master.tryserver.chromium.linux':
            MASTER_TRYSERVER_CHROMIUM_LINUX,
        'chromium/try':
            short_bucket_cfg(LUCI_CHROMIUM_TRY),
        'dart/try':
            short_bucket_cfg(LUCI_DART_TRY),
    }
    self.assertEqual(actual, expected)

  def test_get_buckets_async_with_bucket_ids(self):
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_WIN)
    bid = 'chromium/try'
    actual = config.get_buckets_async([bid]).get_result()
    expected = {'chromium/try': short_bucket_cfg(LUCI_CHROMIUM_TRY)}
    self.assertEqual(actual, expected)

  def test_get_buckets_async_with_bucket_ids_not_found(self):
    bid = 'chromium/try'
    actual = config.get_buckets_async([bid]).get_result()
    self.assertEqual(actual, {bid: None})

  def resolve_bucket(self, bucket_name):
    return config.resolve_bucket_name_async(bucket_name).get_result()

  def test_resolve_bucket_name_async_does_not_exist(self):
    self.assertIsNone(self.resolve_bucket('try'))

  def test_resolve_bucket_name_async_unique(self):
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    self.assertEqual(self.resolve_bucket('try'), 'chromium/try')

  def test_resolve_bucket_name_async_ambiguous(self):
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    config.put_bucket('dart', 'deadbeef', LUCI_DART_TRY)
    with self.assertRaisesRegexp(errors.InvalidInputError, r'ambiguous'):
      self.resolve_bucket('try')

  def test_resolve_bucket_name_async_cache_key(self):
    config.put_bucket('chromium', 'deadbeef', LUCI_CHROMIUM_TRY)
    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_LINUX)
    self.assertEqual(self.resolve_bucket('try'), 'chromium/try')
    self.assertEqual(
        self.resolve_bucket('master.tryserver.chromium.linux'),
        'chromium/master.tryserver.chromium.linux'
    )

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets(self, get_project_configs):
    chromium_buildbucket_cfg = parse_cfg(
        '''
      acl_sets {
        name: "public"
        acls {
          role: READER
          group: "all"
        }
        acls {
          role: READER
          group: "all"
        }
      }
      builder_mixins {
        name: "recipe-x"
        recipe {
          repository: "https://example.com"
          name: "x"
        }
      }
      buckets {
        name: "luci.chromium.try"
        acl_sets: "public"
        swarming {
          builder_defaults {
            mixins: "recipe-x"
          }
          builders {
            name: "linux"
            dimensions: "os:Linux"
          }
        }
      }
      buckets {
        name: "master.tryserver.chromium.linux"
        acl_sets: "public"
        acl_sets: "undefined_acl_set_will_cause_an_error_in_log_but_not_failure"
        acls {
          role: SCHEDULER
          group: "tryjob-access"
        }
      }

      buckets {
        name: "master.tryserver.chromium.win"
        acls {
          role: READER
          group: "all"
        }
        acls {
          role: SCHEDULER
          group: "tryjob-access"
        }
      }
      '''
    )

    dart_buildbucket_cfg = parse_cfg(
        '''
      buckets {
        name: "luci.dart.try"
        swarming {
          builder_defaults {
            dimensions: "pool:Dart.LUCI"
            recipe {
              repository: "https://example.com"
              name: "x"
            }
          }
          builders {
            name: "linux"
          }
        }
      }
      '''
    )

    v8_buildbucket_cfg = parse_cfg(
        '''
      buckets {
        name: "master.tryserver.v8"
        acls {
          role: WRITER
          group: "v8-team"
        }
      }
      '''
    )

    test_buildbucket_cfg = parse_cfg(
        '''
      buckets {
        name: "master.tryserver.test"
        acls {
          role: WRITER
          identity: "root@google.com"
        }
      }
      '''
    )

    get_project_configs.return_value = {
        'chromium': ('deadbeef', chromium_buildbucket_cfg, None),
        'dart': ('deadbeef', dart_buildbucket_cfg, None),
        'v8': (None, v8_buildbucket_cfg, None),
        'test': ('babe', test_buildbucket_cfg, None),
    }

    config.cron_update_buckets()

    actual = config.LegacyBucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key)
    expected = [
        config.LegacyBucket(
            id='luci.chromium.try',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='chromium',
            revision='deadbeef',
            config_content=to_text(LUCI_CHROMIUM_TRY),
            config_content_binary=to_binary(LUCI_CHROMIUM_TRY),
        ),
        config.LegacyBucket(
            id='luci.dart.try',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='dart',
            revision='deadbeef',
            config_content=to_text(LUCI_DART_TRY),
            config_content_binary=to_binary(LUCI_DART_TRY),
        ),
        config.LegacyBucket(
            id='master.tryserver.chromium.linux',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='chromium',
            revision='deadbeef',
            config_content=to_text(MASTER_TRYSERVER_CHROMIUM_LINUX),
            config_content_binary=to_binary(MASTER_TRYSERVER_CHROMIUM_LINUX),
        ),
        config.LegacyBucket(
            id='master.tryserver.chromium.win',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='chromium',
            revision='deadbeef',
            config_content=to_text(MASTER_TRYSERVER_CHROMIUM_WIN),
            config_content_binary=to_binary(MASTER_TRYSERVER_CHROMIUM_WIN),
        ),
        config.LegacyBucket(
            id='master.tryserver.test',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='test',
            revision='babe',
            config_content=to_text(MASTER_TRYSERVER_TEST),
            config_content_binary=to_binary(MASTER_TRYSERVER_TEST),
        ),
        config.LegacyBucket(
            id='master.tryserver.v8',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='v8',
            revision='sha1:cfc761d7a953a72ddea8f3d4c9a28e69777ca22c',
            config_content=to_text(MASTER_TRYSERVER_V8),
            config_content_binary=to_binary(MASTER_TRYSERVER_V8),
        ),
    ]
    self.assertEqual(actual, expected)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets_with_existing(self, get_project_configs):
    chromium_buildbucket_cfg = parse_cfg(
        '''
      buckets {
        name: "master.tryserver.chromium.linux"
        acls {
          role: READER
          group: "all"
        }
        acls {
          role: SCHEDULER
          group: "tryjob-access"
        }
      }

      buckets {
        name: "master.tryserver.chromium.mac"
        acls {
          role: READER
          group: "all"
        }
        acls {
          role: SCHEDULER
          group: "tryjob-access"
        }
      }
      '''
    )

    v8_buildbucket_cfg = parse_cfg(
        '''
      buckets {
        name: "master.tryserver.chromium.linux"
        acls {
          role: WRITER
          group: "v8-team"
        }
      }

      buckets {
        name: "master.tryserver.v8"
        acls {
          role: WRITER
          group: "v8-team"
        }
      }
      '''
    )
    get_project_configs.return_value = {
        'chromium': ('new!', chromium_buildbucket_cfg, None),
        'v8': ('deadbeef', v8_buildbucket_cfg, None),
    }

    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_LINUX)
    # Will not be updated.
    config.put_bucket('v8', 'deadbeef', MASTER_TRYSERVER_V8)
    # Will be deleted.
    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_WIN)

    config.cron_update_buckets()

    actual = config.LegacyBucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key.id())
    expected = [
        config.LegacyBucket(
            id='master.tryserver.chromium.linux',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='chromium',
            revision='new!',
            config_content=to_text(MASTER_TRYSERVER_CHROMIUM_LINUX),
            config_content_binary=to_binary(MASTER_TRYSERVER_CHROMIUM_LINUX),
        ),
        config.LegacyBucket(
            id='master.tryserver.chromium.mac',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='chromium',
            revision='new!',
            config_content=to_text(MASTER_TRYSERVER_CHROMIUM_MAC),
            config_content_binary=to_binary(MASTER_TRYSERVER_CHROMIUM_MAC),
        ),
        config.LegacyBucket(
            id='master.tryserver.v8',
            entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
            project_id='v8',
            revision='deadbeef',
            config_content=to_text(MASTER_TRYSERVER_V8),
            config_content_binary=to_binary(MASTER_TRYSERVER_V8),
        ),
    ]
    self.assertEqual(actual, expected)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets_with_broken_configs(self, get_project_configs):
    config.put_bucket('chromium', 'deadbeef', MASTER_TRYSERVER_CHROMIUM_LINUX)

    get_project_configs.return_value = {
        'chromium': (
            'new!', None, config_component.ConfigFormatError('broken!')
        ),
    }

    config.cron_update_buckets()

    # We must not delete buckets defined in a project that currently have a
    # broken config.
    actual = config.LegacyBucket.get_by_id(MASTER_TRYSERVER_CHROMIUM_LINUX.name)
    self.assertEqual(
        actual.config_content, to_text(MASTER_TRYSERVER_CHROMIUM_LINUX)
    )

  def cfg_validation_test(self, cfg, expected_messages):
    ctx = config_component.validation.Context()
    ctx.config_set = 'projects/chromium'
    config.validate_buildbucket_cfg(cfg, ctx)
    self.assertEqual(expected_messages, ctx.result().messages)

  def test_validate_buildbucket_cfg_success(self):
    self.cfg_validation_test(
        parse_cfg(
            '''
      acl_sets {
        name: "public"
        acls {
          role: READER
          group: "all"
        }
      }
      buckets {
        name: "good.name"
        acls {
          role: WRITER
          group: "writers"
        }
      }
      buckets {
        name: "good.name2"
        acl_sets: "public"
        acls {
          role: READER
          identity: "a@a.com"
        }
        acls {
          role: READER
          identity: "user:b@a.com"
        }
      }
      '''
        ), []
    )

  def test_validate_buildbucket_cfg_swarming(self):
    flatten_builder_mock_with_cloned_args = mock.Mock()
    orig_flatten_builder = flatten_swarmingcfg.flatten_builder

    def flatten_builder(builder, defaults, mixin):
      flatten_builder_mock_with_cloned_args(
          copy.deepcopy(builder),
          copy.deepcopy(defaults),
          copy.deepcopy(mixin),
      )
      orig_flatten_builder(builder, defaults, mixin)

    self.patch(
        'swarming.flatten_swarmingcfg.flatten_builder',
        autospec=True,
        side_effect=flatten_builder
    )

    cfg = parse_cfg(
        '''
      acl_sets {
        name: "public"
        acls {
          role: READER
          group: "all"
        }
      }
      builder_mixins {
        name: "m"
        recipe {
          repository: "https://chromium.googlesource.com/infra/infra"
        }
      }
      buckets {
        name: "luci.chromium.continuous"
        acl_sets: "public"
        swarming {
          hostname: "swarming.example.com"
          builder_defaults {
            dimensions: "pool:P"
          }
          builders {
            name: "builder"
            mixins: "m"
            recipe {
              name: "r"
            }
          }
        }
      }
      '''
    )
    self.cfg_validation_test(copy.deepcopy(cfg), [])

    flatten_builder_mock_with_cloned_args.assert_any_call(
        cfg.buckets[0].swarming.builders[0],
        cfg.buckets[0].swarming.builder_defaults,
        {
            'm': cfg.builder_mixins[0],
        },
    )

  def test_validate_buildbucket_cfg_fail(self):
    self.cfg_validation_test(
        parse_cfg(
            '''
      acl_sets {}
      acl_sets {
        name: "^"
        acls {}
      }
      acl_sets { name: "a" }
      acl_sets { name: "a" }
      buckets {
        name: "a"
        acl_sets: "does_not_exist"
        acls {
          role: READER
          group: "writers"
          identity: "a@a.com"
        }
        acls {
          role: READER
        }
      }
      buckets {
        name: "a"
        acls {
          role: READER
          identity: "ldap"
        }
        acls {
          role: READER
          group: ";%:"
        }
      }
      buckets {}
      buckets { name: "luci.x" }
      '''
        ), [
            errmsg('ACL set #1 (): name is unspecified'),
            errmsg(
                'ACL set #2 (^): invalid name "^" does not match regex '
                '\'^[a-z0-9_]+$\''
            ),
            errmsg('ACL set #2 (^): acl #1: group or identity must be set'),
            errmsg('ACL set #4 (a): duplicate name "a"'),
            errmsg(
                'Bucket a: acl #1: either group or identity must be set, '
                'not both'
            ),
            errmsg('Bucket a: acl #2: group or identity must be set'),
            errmsg(
                'Bucket a: undefined ACL set "does_not_exist". '
                'It must be defined in the same file'
            ),
            errmsg('Bucket a: duplicate bucket name'),
            errmsg('Bucket a: acl #1: Identity has invalid format: ldap'),
            errmsg('Bucket a: acl #2: invalid group: ;%:'),
            errmsg('Bucket #3: invalid name: Bucket not specified'),
            errmsg(
                'Bucket luci.x: invalid name: Bucket must start with '
                '"luci.chromium." because it starts with "luci." and is defined'
                ' in the chromium project'
            ),
        ]
    )

  def test_validate_buildbucket_cfg_unsorted(self):
    self.cfg_validation_test(
        parse_cfg(
            '''
            buckets { name: "c" }
            buckets { name: "b" }
            buckets { name: "a" }
            '''
        ),
        [
            validation_context.Message(
                severity=logging.WARNING,
                text='Bucket b: out of order',
            ),
            validation_context.Message(
                severity=logging.WARNING,
                text='Bucket a: out of order',
            ),
        ],
    )

  @mock.patch('components.config.get_config_set_location', autospec=True)
  def test_get_buildbucket_cfg_url(self, get_config_set_location):
    get_config_set_location.return_value = (
        'https://chromium.googlesource.com/chromium/src/+/infra/config'
    )

    url = config.get_buildbucket_cfg_url('chromium')
    self.assertEqual(
        url, (
            'https://chromium.googlesource.com/chromium/src/+/'
            'refs/heads/infra/config/testbed-test.cfg'
        )
    )

  def test_is_swarming_config(self):
    cfg = project_config_pb2.Bucket()
    self.assertFalse(config.is_swarming_config(cfg))

    cfg.swarming.hostname = 'exists.now'
    self.assertTrue(config.is_swarming_config(cfg))


class ValidateBucketIDTest(testing.AppengineTestCase):

  @parameterized.expand([
      ('chromium',),
      ('chromium/try',),
      ('chrome-internal/try',),
      ('chrome-internal/try.x',),
  ])
  def test_valid(self, bucket_id):
    config.validate_bucket_id(bucket_id)

  @parameterized.expand([
      ('a/b/c',),
      ('a:b',),
      ('a b',),
      ('a b/c',),
      ('chromium/luci.chromium.try',),
  ])
  def test_invalid(self, bucket_id):
    with self.assertRaises(errors.InvalidInputError):
      config.validate_bucket_id(bucket_id)
