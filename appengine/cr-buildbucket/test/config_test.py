# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from components import config as config_component
from components.config import validation_context
from testing_utils import testing
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


class ConfigTest(testing.AppengineTestCase):
  def test_get_bucket_async(self):
    config.Bucket(
      id='master.tryserver.chromium.linux',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT).put()
    cfg = config.get_bucket_async(
      'master.tryserver.chromium.linux').get_result()
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

    self.assertIsNone(config.get_bucket_async('non.existing').get_result())

  def test_get_buckets_async(self):
    config.Bucket(
      id='master.tryserver.chromium.linux',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT).put()
    config.Bucket(
      id='master.tryserver.chromium.win',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT).put()
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
    chromium_buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[
        project_config_pb2.Bucket(
          name='master.tryserver.chromium.linux',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ],
        ),
        project_config_pb2.Bucket(
          name='master.tryserver.chromium.win',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ],
        ),
      ])

    v8_buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[
        project_config_pb2.Bucket(
          name='master.tryserver.v8',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.WRITER, group='v8-team')
          ],
        ),
      ]
    )

    test_buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[
        project_config_pb2.Bucket(
          name='master.tryserver.test',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.WRITER, identity='root@google.com')
          ],
        ),
      ]
    )

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
      ),
      config.Bucket(
        id='master.tryserver.chromium.win',
        project_id='chromium',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
      ),
      config.Bucket(
        id='master.tryserver.test',
        project_id='test',
        revision='babe',
        config_content=MASTER_TRYSERVER_TEST_CONFIG_TEXT
      ),
      config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='sha1:cfc761d7a953a72ddea8f3d4c9a28e69777ca22c',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
      ),
    ]
    self.assertEqual(actual, expected)

  def test_cron_update_buckets_with_existing(self):
    config.Bucket(
      id='master.tryserver.chromium.linux',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_LINUX_CONFIG_TEXT,
    ).put()

    # Will not be updated.
    config.Bucket(
      id='master.tryserver.v8',
      project_id='v8',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
    ).put()

    # Will be deleted.
    config.Bucket(
      id='master.tryserver.chromium.win',
      project_id='chromium',
      revision='deadbeef',
      config_content=MASTER_TRYSERVER_CHROMIUM_WIN_CONFIG_TEXT,
    ).put()

    chromium_buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[
        project_config_pb2.Bucket(
          name='master.tryserver.chromium.linux',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ],
        ),
        # Will be added.
        project_config_pb2.Bucket(
          name='master.tryserver.chromium.mac',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.READER, group='all'),
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.SCHEDULER, group='tryjob-access'),
          ],
        ),
      ])

    v8_buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[
        # Reservation will fail.
        project_config_pb2.Bucket(
          name='master.tryserver.chromium.linux',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.WRITER, group='v8-team')
          ],
        ),
        # Will not be updated.
        project_config_pb2.Bucket(
          name='master.tryserver.v8',
          acls=[
            project_config_pb2.Acl(
              role=project_config_pb2.Acl.WRITER, group='v8-team')
          ],
        ),
      ],
    )

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
      ),
      config.Bucket(
        id='master.tryserver.chromium.mac',
        project_id='chromium',
        revision='new!',
        config_content=MASTER_TRYSERVER_CHROMIUM_MAC_CONFIG_TEXT,
      ),
      config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='deadbeef',
        config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT,
      ),
    ]
    self.assertEqual(actual, expected)

  def test_cron_update_buckets_change_reservation(self):
    config.Bucket(
      id='bucket',
      project_id='foo',
      revision='deadbeef',
      config_content='name: "bucket"',
    ).put()

    buildbucket_cfg = project_config_pb2.BuildbucketCfg(
      buckets=[project_config_pb2.Bucket(name='bucket')]
    )
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
      )
    ]
    self.assertEqual(actual, expected)

  def cfg_validation_test(self, cfg, expected_messages):
    ctx = config_component.validation.Context()
    ctx.config_set = 'projects/chromium'
    config.validate_buildbucket_cfg(cfg, ctx)
    self.assertEqual(expected_messages, ctx.result().messages)

  def test_validate_buildbucket_cfg_success(self):
    self.cfg_validation_test(
      project_config_pb2.BuildbucketCfg(
        buckets=[
          project_config_pb2.Bucket(
            name='good.name',
            acls=[
              project_config_pb2.Acl(
                group='writers', role=project_config_pb2.Acl.WRITER)
            ],
          ),
          project_config_pb2.Bucket(
            name='good.name2',
            acls=[
              project_config_pb2.Acl(
                identity='a@a.com', role=project_config_pb2.Acl.READER),
              project_config_pb2.Acl(
                identity='user:b@a.com', role=project_config_pb2.Acl.READER),
            ],
          )
        ]),
      []
    )

  def test_validate_buildbucket_cfg_fail(self):
    self.cfg_validation_test(
      project_config_pb2.BuildbucketCfg(
        buckets=[
          project_config_pb2.Bucket(
            name='a',
            acls=[
              project_config_pb2.Acl(
                group='writers', identity='a@a.com',
                role=project_config_pb2.Acl.READER),
              project_config_pb2.Acl(role=project_config_pb2.Acl.READER),
            ]
          ),
          project_config_pb2.Bucket(
            name='b',
            acls=[
              project_config_pb2.Acl(
                identity='ldap', role=project_config_pb2.Acl.READER),
              project_config_pb2.Acl(
                group='a@a.com', role=project_config_pb2.Acl.READER),
            ]
          ),
          project_config_pb2.Bucket(),
        ]),
      [
        errmsg(
          'Bucket a: acl #1: either group or identity must be set, '
          'not both'),
        errmsg('Bucket a: acl #2: group or identity must be set'),
        errmsg('Bucket b: acl #1: Identity has invalid format: ldap'),
        errmsg('Bucket b: acl #2: invalid group: a@a.com'),
        errmsg('Bucket #3: invalid name: Bucket not specified'),
      ]
    )

  def test_validate_buildbucket_cfg_unsorted(self):
    self.cfg_validation_test(
      project_config_pb2.BuildbucketCfg(
        buckets=[
          project_config_pb2.Bucket(name='b'),
          project_config_pb2.Bucket(name='a')
        ]),
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
      config_content=MASTER_TRYSERVER_V8_CONFIG_TEXT).put()

    self.cfg_validation_test(
      project_config_pb2.BuildbucketCfg(
        buckets=[
          project_config_pb2.Bucket(name='a'),
          project_config_pb2.Bucket(name='a'),
          project_config_pb2.Bucket(name='master.tryserver.chromium.linux'),
          project_config_pb2.Bucket(name='master.tryserver.v8'),
        ]),
      [
        errmsg('Bucket a: duplicate bucket name'),
        errmsg(
          'Bucket master.tryserver.v8: '
          'this name is already reserved by another project'),
      ]
    )


def errmsg(text):
  return validation_context.Message(severity=logging.ERROR, text=text)
