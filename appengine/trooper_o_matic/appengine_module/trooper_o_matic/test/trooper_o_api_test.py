# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import unittest
import webapp2
import webtest

import endpoints
from protorpc import protojson

from appengine_module.trooper_o_matic import controller
from appengine_module.trooper_o_matic import cron
from appengine_module.trooper_o_matic import models
from appengine_module.trooper_o_matic import trooper_o_api
from appengine_module.trooper_o_matic.test import testing_common
from appengine_module.trooper_o_matic.test import test_data
from appengine_module.testing_utils import testing


def MockNow():
  return datetime.datetime(2014, 1, 1, 12)


class ApiTest(testing.AppengineTestCase):

  def setUp(self):  # pylint: disable=E1002
    super(ApiTest, self).setUp()
    # restricted=False is needed for testing.
    # Initialized here because setUp() has to be run first.
    self.app_module = endpoints.api_server(
        [trooper_o_api.TrooperOMaticAPI],
        restricted=False
    )

    testing_common.StubUrlfetch(test_data.URLFETCH_RESPONSES,
                                stub=self.testbed.get_stub('urlfetch'))

    cron.datetime_now = MockNow


  def _make_api_call(self, method, params=None, status=None):
    params = params or {}
    return self.test_app.post_json(
        '/_ah/spi/TrooperOMaticAPI.%s' % method,
        params=params,
        status=status,
    )

  def testCqStats(self):
    project = 'chromium'
    cron_app = webtest.TestApp(
        webapp2.WSGIApplication([
          ('/check-cq', cron.CheckCQHandler),
        ])
    )
    cron_app.get('/check-cq')
    cq_data = self._make_api_call(
        'cq_stats_get',
        params={'project': project},
    ).json

    generated = {}
    for name, klass in (('single_run_data', models.CqStat),
                        ('queue_time_data', models.CqTimeInQueueForPatchStat),
                        ('total_time_data', models.CqTotalTimeForPatchStat)):
      generated[name] = [
        protojson.decode_message(klass.ProtoModel(), json.dumps(x))
        for x in cq_data[name]]

    expected = controller.get_cq_stats(project)
    for key in expected:
      expected[key] = [x.ToMessage() for x in expected[key]]

    self.assertEqual(generated, expected)


if __name__ == '__main__':
  unittest.main()
