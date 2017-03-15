# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import auth
from components import auth_testing
from testing_utils import testing

from test import config_test
import config
import swarming

class SwarmbucketApiTest(testing.EndpointsTestCase):
  api_service_cls = swarming.SwarmbucketApi

  def test_get_builders(self):
    auth_testing.reset_local_state()
    auth.bootstrap_group('all', [auth.Anonymous])

    chromium_cfg = '''
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
    '''
    config.Bucket(
      id='master.tryserver.chromium',
      project_id='chromium',
      revision='deadbeef',
      config_content=chromium_cfg,
      config_content_binary=config_test.text_to_binary(chromium_cfg),
    ).put()

    v8_cfg = '''
      name: "master.tryserver.v8"
      acls {
        role: READER
        group: "all"
      }
    '''
    config.Bucket(
      id='master.tryserver.v8',
      project_id='v8',
      revision='deadbeef',
      config_content=v8_cfg,
      config_content_binary=config_test.text_to_binary(v8_cfg),
    ).put()

    secret_cfg = 'name: "secret"'
    config.Bucket(
      id='secret',
      project_id='secret',
      revision='deadbeef',
      config_content=secret_cfg,
      config_content_binary=config_test.text_to_binary(secret_cfg),
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
