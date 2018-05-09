# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import utils
utils.fix_protobuf_package()

from google.appengine.ext import ndb
from testing_utils import testing

from proto import project_config_pb2
import protoutil


class ProtoUtilTest(testing.AppengineTestCase):

  def test_unmarshal_dict(self):
    msg = project_config_pb2.Swarming()
    data = {
        'builder_defaults': {
            'dimensions': ['a:a', 'b:b'],
            'execution_timeout_secs': 600,
            'recipe': {
                'name': 'trybot',
            },
        },
        'builders': [
            {
                'name': 'debug'
            },
            {
                'name': 'release'
            },
        ],
    }
    protoutil.merge_dict(data, msg)
    self.assertEqual(msg.builder_defaults.dimensions, ['a:a', 'b:b'])
    self.assertEqual(msg.builder_defaults.execution_timeout_secs, 600)
    self.assertEqual(len(msg.builders), 2)
    self.assertEqual(msg.builders[0].name, 'debug')

    msg = project_config_pb2.Swarming()
    with self.assertRaises(TypeError):
      protoutil.merge_dict([], msg)

    with self.assertRaises(TypeError):
      protoutil.merge_dict({'no_such_field': 0}, msg)

    with self.assertRaises(TypeError):
      protoutil.merge_dict({'builder_defaults': 0}, msg)
