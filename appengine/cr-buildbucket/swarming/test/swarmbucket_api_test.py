# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import auth
from components import auth_testing
from testing_utils import testing

import config
import swarming


class SwarmbucketApiTest(testing.EndpointsTestCase):
  api_service_cls = swarming.SwarmbucketApi

  def test_get_builders(self):
    auth_testing.reset_local_state()
    auth.bootstrap_group('all', [auth.Anonymous])
    config.Bucket(
      id='master.tryserver.chromium',
      project_id='chromium',
      revision='deadbeef',
      config_content="""
        name: "master.tryserver.chromium"
        acls {
          role: READER
          group: "all"
        }
        swarming {
          builders {
            name: "Windows"
            category: "Chromium"
          }
          builders {
            name: "Linux"
            category: "Chromium"
          }
        }
      """,
    ).put()

    config.Bucket(
        id='master.tryserver.v8',
        project_id='v8',
        revision='deadbeef',
        config_content="""
          name: "master.tryserver.v8"
          acls {
            role: READER
            group: "all"
          }
        """,
    ).put()

    config.Bucket(
        id='secret',
        project_id='secret',
        revision='deadbeef',
        config_content='name: "secret"',
    ).put()

    resp = self.call_api('get_builders').json_body
    self.assertEqual(resp, {
      'buckets': [
        {
          'name': 'master.tryserver.chromium',
          'builders': [
            {'name': 'Windows', 'category': 'Chromium'},
            {'name': 'Linux', 'category': 'Chromium'},
          ]
        }
      ]
    })
