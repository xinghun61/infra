# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from components import utils


utils.fix_protobuf_package()

from components import config as config_component
from components.config import validation_context
from testing_utils import testing
from google import protobuf
import mock

from proto import project_config_pb2
import config

LUCI_CHROMIUM_TRY_CONFIG_TEXT = (
'''name: "luci.chromium.try"
acls {
  role: READER
  group: "all"
}
swarming {
  builders {
    name: "release"
    dimensions: "os:Linux"
    dimensions: "pool:default"
    recipe {
      repository: "https://example.com"
      name: "x"
    }
  }
}
''')

MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT = (
'''name: "master.tryserver.chromium.linux"
acls {
  role: READER
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
''')

MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT = (
'''name: "master.tryserver.chromium.win"
acls {
  role: READER
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
''')

MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT = (
'''name: "master.tryserver.chromium.mac"
acls {
  role: READER
  group: "all"
}
acls {
  role: SCHEDULER
  group: "tryjob-access"
}
''')

MASTER_TRYSERVER_V8_CONFIG_TEXT = (
'''name: "master.tryserver.v8"
acls {
  role: WRITER
  group: "v8-team"
}
''')

MASTER_TRYSERVER_TEST_CONFIG_TEXT = (
'''name: "master.tryserver.test"
acls {
  role: WRITER
  identity: "user:root@google.com"
}
''')

def parse_cfg(text):
  cfg = project_config_pb2.BuildbucketCfg()
  protobuf.text_format.Merge(text, cfg)
  return cfg


def text_to_binary(bucket_cfg_text):
  cfg = project_config_pb2.Bucket()
  protobuf.text_format.Merge(bucket_cfg_text, cfg)
  return cfg.SerializeToString()


def errmsg(text):
  return validation_context.Message(severity=logging.ERROR, text=text)


class ConfigTest(testing.AppengineTestCase):
  def test_get_bucket(self):
    config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
    ).put()
    project, cfg = config.get_bucket('master.tryserver.chromium.linux')
    self.assertEqual(project, 'chromium')
    self.assertEqual(
        cfg,
        project_config_pb2.Bucket(
            name='master.tryserver.chromium.linux',
            acls=[
              project_config_pb2.Acl(
                  role=project_config_pb2.Acl.READER, group='all'),
              project_config_pb2.Acl(
                  role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
            ]),
    )

    self.assertIsNone(config.get_bucket('non.existing')[0])

  def test_get_bucket_async(self):
    config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
    ).put()
    project, cfg = config.get_bucket_async(
        'master.tryserver.chromium.linux').get_result()
    self.assertEqual(project, 'chromium')
    self.assertEqual(
        cfg,
        project_config_pb2.Bucket(
            name='master.tryserver.chromium.linux',
            acls=[
              project_config_pb2.Acl(
                  role=project_config_pb2.Acl.READER, group='all'),
              project_config_pb2.Acl(
                  role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
            ]),
    )

    self.assertIsNone(config.get_bucket_async('non.existing').get_result()[0])

  def test_get_buckets_async(self):
    config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT)).put()
    config.Bucket(
        id='master.tryserver.chromium.win',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT)).put()
    actual = config.get_buckets_async().get_result()
    expected = [
      project_config_pb2.Bucket(
          name='master.tryserver.chromium.linux',
          acls=[
            project_config_pb2.Acl(
                role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
                role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ]),
      project_config_pb2.Bucket(
          name='master.tryserver.chromium.win',
          acls=[
            project_config_pb2.Acl(
                role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
                role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ]),
    ]
    self.assertEqual(actual, expected)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets(self, get_project_configs):
    chromium_buildbucket_cfg = parse_cfg('''
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
            dimensions: "pool:default"
          }
          builders {
            name: "release"
            mixins: "recipe-x"
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
      ''')

    v8_buildbucket_cfg = parse_cfg('''
      buckets {
        name: "master.tryserver.v8"
        acls {
          role: WRITER
          group: "v8-team"
        }
      }
      ''')

    test_buildbucket_cfg = parse_cfg('''
      buckets {
        name: "master.tryserver.test"
        acls {
          role: WRITER
          identity: "root@google.com"
        }
      }
      ''')

    get_project_configs.return_value = {
      'chromium': ('deadbeef', chromium_buildbucket_cfg, None),
      'v8': (None, v8_buildbucket_cfg, None),
      'test': ('babe', test_buildbucket_cfg, None),
    }

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key)
    expected = [
      config.Bucket(
          id='luci.chromium.try',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='chromium',
          revision='deadbeef',
          config_content=LUCI_CHROMIUM_TRY_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              LUCI_CHROMIUM_TRY_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.chromium.linux',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='chromium',
          revision='deadbeef',
          config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.chromium.win',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='chromium',
          revision='deadbeef',
          config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.test',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='test',
          revision='babe',
          config_content=MASTER_TRYSERVER_TEST_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              MASTER_TRYSERVER_TEST_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.v8',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='v8',
          revision='sha1:cfc761d7a953a72ddea8f3d4c9a28e69777ca22c',
          config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
          config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
      ),
    ]
    self.assertEqual(actual, expected)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets_with_existing(self, get_project_configs):
    chromium_buildbucket_cfg = parse_cfg('''
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
      ''')

    v8_buildbucket_cfg = parse_cfg('''
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
      ''')
    get_project_configs.return_value = {
      'chromium': ('new!', chromium_buildbucket_cfg, None),
      'v8': ('deadbeef', v8_buildbucket_cfg, None),
    }

    config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
    ).put()

    # Will not be updated.
    config.Bucket(
        id='master.tryserver.v8',
        entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
        project_id='v8',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
        config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
    ).put()

    # Will be deleted.
    config.Bucket(
        id='master.tryserver.chromium.win',
        entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT),
    ).put()

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key.id())
    expected = [
      config.Bucket(
          id='master.tryserver.chromium.linux',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='chromium',
          revision='new!',
          config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.chromium.mac',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='chromium',
          revision='new!',
          config_content=MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT,
          config_content_binary=text_to_binary(
              MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT),
      ),
      config.Bucket(
          id='master.tryserver.v8',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='v8',
          revision='deadbeef',
          config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
          config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
      ),
    ]
    self.assertEqual(actual, expected)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets_with_broken_configs(self, get_project_configs):
    bucket = config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
            MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
    )
    bucket.put()

    get_project_configs.return_value = {
      'chromium': ('new!', None, config_component.ConfigFormatError('broken!')),
    }

    config.cron_update_buckets()

    # We must not delete buckets defined in a project that currently have a
    # broken config.
    actual = bucket.key.get()
    self.assertEqual(bucket, actual)

  @mock.patch('components.config.get_project_configs', autospec=True)
  def test_cron_update_buckets_change_reservation(self, get_project_configs):
    buildbucket_cfg = parse_cfg('''buckets{ name: "bucket" }''')
    get_project_configs.return_value = {
      'bar': ('deadbeef', buildbucket_cfg, None),
    }

    config.Bucket(
        id='bucket',
        project_id='foo',
        revision='deadbeef',
        config_content='name: "bucket"',
        config_content_binary=text_to_binary('name: "bucket"'),
    ).put()

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    expected = [
      config.Bucket(
          id='bucket',
          entity_schema_version=config.CURRENT_BUCKET_SCHEMA_VERSION,
          project_id='bar',
          revision='deadbeef',
          config_content='name: "bucket"\n',
          config_content_binary=text_to_binary('name: "bucket"\n'),
      )
    ]
    self.assertEqual(actual, expected)

  def cfg_validation_test(self, cfg, expected_messages):
    ctx = config_component.validation.Context()
    ctx.config_set = 'projects/chromium'
    config.validate_buildbucket_cfg(cfg, ctx)
    self.assertEqual(expected_messages, ctx.result().messages)

  def test_validate_buildbucket_cfg_success(self):
    self.cfg_validation_test(parse_cfg('''
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
      '''), [])

  def test_validate_buildbucket_cfg_fail(self):
    self.cfg_validation_test(parse_cfg('''
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
        name: "b"
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
      '''),
        [
          errmsg('ACL set #1 (): name is unspecified'),
          errmsg(
              'ACL set #2 (^): invalid name "^" does not match regex '
              '\'^[a-z0-9_]+$\''),
          errmsg('ACL set #2 (^): acl #1: group or identity must be set'),
          errmsg('ACL set #4 (a): duplicate name "a"'),
          errmsg(
              'Bucket a: acl #1: either group or identity must be set, '
              'not both'),
          errmsg('Bucket a: acl #2: group or identity must be set'),
          errmsg(
              'Bucket a: undefined ACL set "does_not_exist". '
              'It must be defined in the same file'),
          errmsg('Bucket b: acl #1: Identity has invalid format: ldap'),
          errmsg('Bucket b: acl #2: invalid group: ;%:'),
          errmsg('Bucket #3: invalid name: Bucket not specified'),
          errmsg(
              'Bucket luci.x: invalid name: Bucket must start with '
              '"luci.chromium." because it starts with "luci." and is defined '
              'in the chromium project'),
        ]
    )

  def test_validate_buildbucket_cfg_unsorted(self):
    self.cfg_validation_test(parse_cfg('''
      buckets { name: "b" }
      buckets { name: "a" }
      '''),
        [
          validation_context.Message(
              severity=logging.WARNING,
              text='Buckets are not sorted by name'),
        ]
    )

  def test_validate_buildbucket_cfg_duplicate_names(self):
    config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
        config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
    ).put()

    self.cfg_validation_test(
        parse_cfg('''
          buckets { name: "a" }
          buckets { name: "a" }
          buckets { name: "master.tryserver.chromium.linux" }
          buckets { name: "master.tryserver.v8" }
      '''),
        [
          errmsg('Bucket a: duplicate bucket name'),
          errmsg(
              'Bucket master.tryserver.v8: '
              'this name is already reserved by another project'),
        ]
    )

  @mock.patch('components.config.get_config_set_location', autospec=True)
  def test_get_buildbucket_cfg_url(self, get_config_set_location):
    get_config_set_location.return_value = (
      'https://chromium.googlesource.com/chromium/src/+/infra/config')

    url = config.get_buildbucket_cfg_url('chromium')
    self.assertEqual(
        url,
        ('https://chromium.googlesource.com/chromium/src/+/'
         'infra/config/testbed-test.cfg'))

  def test_is_swarming_config(self):
    cfg = project_config_pb2.Bucket()
    self.assertFalse(config.is_swarming_config(cfg))

    cfg.swarming.hostname = 'exists.now'
    self.assertTrue(config.is_swarming_config(cfg))
