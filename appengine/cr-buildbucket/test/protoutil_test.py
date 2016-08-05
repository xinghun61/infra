# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from testing_utils import testing

from proto import project_config_pb2
import protoutil


class JsonpbTest(testing.AppengineTestCase):
  def test_unmarshal_dict(self):
    msg = project_config_pb2.Swarming()
    data = {
      'common_dimensions': ['a:a', 'b:b'],
      'common_execution_timeout_secs': 600,
      'common_recipe': {
        'name': 'trybot',
      },
      'builders': [
        {'name': 'debug'},
        {'name': 'release'},
      ],
    }
    protoutil.merge_dict(data, msg)
    self.assertEqual(msg.common_dimensions, ['a:a', 'b:b'])
    self.assertEqual(msg.common_execution_timeout_secs, 600)
    self.assertEqual(len(msg.builders), 2)
    self.assertEqual(msg.builders[0].name, 'debug')

    msg = project_config_pb2.Swarming()
    with self.assertRaises(TypeError):
      protoutil.merge_dict([], msg)

    with self.assertRaises(TypeError):
      protoutil.merge_dict({'no_such_field': 0}, msg)

    with self.assertRaises(TypeError):
      protoutil.merge_dict({'common_dimensions': 0}, msg)
