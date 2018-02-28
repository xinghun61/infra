# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from services import build_ahead
from waterfall.test import wf_testcase

CN = 'builder_cc0b584fcab5ab502af9c154891c705115ea1fefd4d176cabf5d04ae0cd4e18c'


class BuildAheadTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(buildbucket_client, 'TriggerTryJobs')
  def testBuildAhead(self, mock_trigger):
    _ = build_ahead.TriggerBuildAhead('master2', 'builder5', 'some_bot')
    mock_trigger.assert_called_once_with([
        buildbucket_client.TryJob(
            master_name='luci.chromium.findit',
            builder_name='findit_variable',
            properties={
                'recipe': 'findit/chromium/compile',
                'good_revision': 'HEAD~1',
                'target_mastername': 'master2',
                'mastername': 'tryserver2',
                'suspected_revisions': [],
                'target_buildername': 'builder5',
                'bad_revision': 'HEAD'
            },
            tags=[],
            additional_build_parameters=None,
            cache_name=CN,
            dimensions=[
                'os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit',
                'id:some_bot'
            ],
            pubsub_callback=None)
    ])

  @mock.patch.object(FinditHttpClient, 'Get')
  def testTreeIsOpen(self, mock_get):
    responses = [
        (500, None),
        (400, None),
        (200, None),
        (200, '[]'),
        (200, '[{}]'),
        (200, '[{"general_state":"closed"}]'),
        (200, '[{"general_state":"open"}]'),
    ]
    mock_get.side_effect = responses

    for _ in range(len(responses) - 1):
      self.assertFalse(build_ahead.TreeIsOpen())

    self.assertTrue(build_ahead.TreeIsOpen())
