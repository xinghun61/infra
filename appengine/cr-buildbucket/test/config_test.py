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

  def test_cron_update_buckets(self):
    chromium_buildbucket_cfg = parse_cfg("""
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
      """)

    v8_buildbucket_cfg = parse_cfg("""
      buckets {
        name: "master.tryserver.v8"
        acls {
          role: WRITER
          group: "v8-team"
        }
      }
      """)

    test_buildbucket_cfg = parse_cfg("""
      buckets {
        name: "master.tryserver.test"
        acls {
          role: WRITER
          identity: "root@google.com"
        }
      }
      """)

    self.mock(config_component, 'get_project_configs', mock.Mock())
    config_component.get_project_configs.return_value = {
      'chromium': ('deadbeef', chromium_buildbucket_cfg),
      'v8': (None, v8_buildbucket_cfg),
      'test': ('babe', test_buildbucket_cfg),
    }

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key)
    expected = [
      config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
          MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
      ),
      config.Bucket(
        id='master.tryserver.chromium.win',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
        config_content_binary=text_to_binary(
          MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT),
      ),
      config.Bucket(
        id='master.tryserver.test',
        project_id='test',
        revision='babe',
        config_content=MASTER_TRYSERVER_TEST_CONFIG_TEXT,
        config_content_binary=text_to_binary(MASTER_TRYSERVER_TEST_CONFIG_TEXT),
      ),
      config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='sha1:cfc761d7a953a72ddea8f3d4c9a28e69777ca22c',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
        config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
      ),
    ]
    self.assertEqual(actual, expected)

  def test_cron_update_buckets_with_existing(self):
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
      project_id='v8',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
      config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
    ).put()

    # Will be deleted.
    config.Bucket(
      id='master.tryserver.chromium.win',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
      config_content_binary=text_to_binary(
        MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT),
    ).put()

    chromium_buildbucket_cfg = parse_cfg("""
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
      """)

    v8_buildbucket_cfg = parse_cfg("""
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
      """)

    self.mock(config_component, 'get_project_configs', mock.Mock())
    config_component.get_project_configs.return_value = {
      'chromium': ('new!', chromium_buildbucket_cfg),
      'v8': ('deadbeef', v8_buildbucket_cfg),
    }

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    actual = sorted(actual, key=lambda b: b.key.id())
    expected = [
      config.Bucket(
        id='master.tryserver.chromium.linux',
        project_id='chromium',
        revision='new!',
        config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
        config_content_binary=text_to_binary(
          MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT),
      ),
      config.Bucket(
        id='master.tryserver.chromium.mac',
        project_id='chromium',
        revision='new!',
        config_content=MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT,
        config_content_binary=text_to_binary(
          MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT),
      ),
      config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
        config_content_binary=text_to_binary(MASTER_TRYSERVER_V8_CONFIG_TEXT),
      ),
    ]
    self.assertEqual(actual, expected)

  def test_cron_update_buckets_change_reservation(self):
    config.Bucket(
      id='bucket',
      project_id='foo',
      revision='deadbeef',
      config_content='name: "bucket"',
      config_content_binary=text_to_binary('name: "bucket"'),
    ).put()

    buildbucket_cfg = parse_cfg("""buckets{ name: "bucket" }""")
    self.mock(config_component, 'get_project_configs', mock.Mock())
    config_component.get_project_configs.return_value = {
      'bar': ('deadbeef', buildbucket_cfg),
    }

    config.cron_update_buckets()

    actual = config.Bucket.query().fetch()
    expected = [
      config.Bucket(
        id='bucket',
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
    self.cfg_validation_test(parse_cfg("""
      buckets {
        name: "good.name"
        acls {
          role: WRITER
          group: "writers"
        }
      }
      buckets {
        name: "good.name2"
        acls {
          role: READER
          identity: "a@a.com"
        }
        acls {
          role: READER
          identity: "user:b@a.com"
        }
      }
      """), [])

  def test_validate_buildbucket_cfg_fail(self):
    self.cfg_validation_test(parse_cfg("""
      buckets {
        name: "a"
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
      """),
      [
        errmsg(
          'Bucket a: acl #1: either group or identity must be set, '
          'not both'),
        errmsg('Bucket a: acl #2: group or identity must be set'),
        errmsg('Bucket b: acl #1: Identity has invalid format: ldap'),
        errmsg('Bucket b: acl #2: invalid group: ;%:'),
        errmsg('Bucket #3: invalid name: Bucket not specified'),
      ]
    )

  def test_validate_buildbucket_cfg_unsorted(self):
    self.cfg_validation_test(parse_cfg("""
      buckets { name: "b" }
      buckets { name: "a" }
      """),
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
      parse_cfg("""
          buckets { name: "a" }
          buckets { name: "a" }
          buckets { name: "master.tryserver.chromium.linux" }
          buckets { name: "master.tryserver.v8" }
      """),
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
