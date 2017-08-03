# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import webapp2

import webtest

from handlers import rerun_for_compare
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall.test import wf_testcase


def _GenFakeBuildbucketResponse(master, builder):
  """Make a response object to trick _GetBotFromBuildbucketResponse."""
  parameters = {
      'properties': {
          'good_revision': 1,
          'bad_revision': 100
      },
      'additional_build_parameters': {}
  }
  result = {
      'bucket': master,
      'tags': ['mock:Value', 'builder:' + builder],
      'parameters_json': json.dumps(parameters)
  }
  return result


class RerunForCompareTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/rerun-for-compare', rerun_for_compare.RerunForCompare),
      ], debug=True)

  @mock.patch('gae_libs.token.ValidateAuthToken', return_value=(True, False))
  def testTriggerWaterfallRerun(self, _mock_auth):
    tryjob = WfTryJob.Create('m', 'b1', 1)
    tryjob.put()
    try_job_data = WfTryJobData.Create('12345t')
    try_job_data.try_job_type = 'test'
    try_job_data.try_job_key = tryjob.key
    try_job_data.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'm', 'b')
    try_job_data.put()
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    with mock.patch.object(rerun_for_compare.RerunTryJobPipeline,
                           'start') as mock_pipe:
      self.test_app.post('/rerun-for-compare', params={'try_job': '12345t'})
      self.assertTrue(mock_pipe.called)

  @mock.patch('gae_libs.token.ValidateAuthToken', return_value=(True, False))
  def testTriggerFlakeRerun(self, _mock_auth):
    try_job_data = WfTryJobData.Get('12345f')
    # Because the tests may run out of order, and the test below depends on this
    # not existing.
    if try_job_data:  # pragma: no cover.
      try_job_data.delete()
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    with self.assertRaisesRegexp(webtest.AppError, '.*404.*'):
      self.test_app.post('/rerun-for-compare', params={'try_job': '12345f'})
