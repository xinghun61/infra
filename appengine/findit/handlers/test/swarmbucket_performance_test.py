# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import webapp2

from testing_utils import testing

from libs import time_util
from model.wf_config import FinditConfig
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from handlers import swarmbucket_performance

BUILDER_MAP = {
    'master': {
        'builder1': {
            'mastername': 'chromium',
            'waterfall_trybot': 'builder1',
        },
        'builder2': {
            'swarmbucket_mastername': 'luci.chromium',
            'swarmbucket_trybot': 'swarm_builder2',
        },
        'builder3': {
            'mastername': 'chromium',
            'waterfall_trybot': 'builder3',
            'swarmbucket_mastername': 'luci.chromium',
            'swarmbucket_trybot': 'swarm_builder3',
        },
    }
}


def _GenFakeBuildbucketResponse(master, builder):
  """Make a response object to trick _GetBotFromBuildbucketResponse."""
  result = {'bucket': master, 'tags': ['mock:Value', 'builder:' + builder]}
  return result


class SwarmbucketPerformanceTest(testing.AppengineTestCase):
  masDiff = None
  app_module = webapp2.WSGIApplication(
      [
          ('/swarmbucket_performance',
           swarmbucket_performance.SwarmbucketPerformance),
      ],
      debug=True)

  @mock.patch.object(
      swarmbucket_performance,
      "_GetStartEndDates",
      return_value=(datetime.datetime(2017, 1, 1, 0, 0, 0), datetime.datetime(
          2017, 1, 31, 0, 0, 0)))
  def testFindRecentSwarmbucketJobs(self, *_):
    builders = {'sm/sb': 'tm/tb'}
    irrelevant = WfTryJob.Create('m', 'b2', 1)
    irrelevant_run_1 = WfTryJobData.Create('ir1')
    irrelevant_run_1.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'sm', 'sb2')
    irrelevant_run_1.created_time = datetime.datetime(2017, 1, 2, 0, 0, 0)
    irrelevant_run_1.try_job_key = irrelevant.key
    irrelevant_run_1.put()
    irrelevant.try_job_ids.append('ir1')
    irrelevant.put()

    relevant = WfTryJob.Create('m', 'b', 1)
    swarmbucket_run_1 = WfTryJobData.Create('sbr1')
    swarmbucket_run_1.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'sm', 'sb')
    swarmbucket_run_1.created_time = datetime.datetime(2017, 1, 2, 0, 0, 0)
    swarmbucket_run_1.try_job_key = relevant.key
    swarmbucket_run_1.put()
    relevant.try_job_ids.append('sbr1')
    relevant.put()

    self.assertEqual([{
        'try_job_data': swarmbucket_run_1,
        'builder': 'sm/sb'
    }], swarmbucket_performance._FindRecentSwarmbucketJobs(
        None, None, builders))

  def testFindJobPairs(self):
    builders = {'sm/sb': 'tm/tb'}
    # We need one that has a match and one that doesnt
    # TryJobA has [swarmbucket, swarmbucket, buildbot]
    tryjob_a = WfTryJob.Create('m', 'b2', 1)
    tryjob_a_run_1 = WfTryJobData.Create('tar1')
    tryjob_a_run_1.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'sm', 'sb')
    tryjob_a_run_1.created_time = datetime.datetime(2017, 1, 2, 0, 0, 0)
    tryjob_a_run_1.try_job_key = tryjob_a.key
    tryjob_a_run_1.put()
    tryjob_a.try_job_ids.append('tar1')
    tryjob_a_run_2 = WfTryJobData.Create('tar2')
    tryjob_a_run_2.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'sm', 'sb')
    tryjob_a_run_2.created_time = datetime.datetime(2017, 1, 2, 1, 0, 0)
    tryjob_a_run_2.try_job_key = tryjob_a.key
    tryjob_a_run_2.put()
    tryjob_a.try_job_ids.append('tar2')
    tryjob_a_run_3 = WfTryJobData.Create('tar3')
    tryjob_a_run_3.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'tm', 'tb')
    tryjob_a_run_3.created_time = datetime.datetime(2017, 1, 2, 3, 0, 0)
    tryjob_a_run_3.try_job_key = tryjob_a.key
    tryjob_a_run_3.put()
    tryjob_a.try_job_ids.append('tar3')
    tryjob_a.put()

    # TryjobB has [swarmbucket only]
    tryjob_b = WfTryJob.Create('m', 'b3', 1)
    tryjob_b_run_1 = WfTryJobData.Create('tbr1')
    tryjob_b_run_1.last_buildbucket_response = _GenFakeBuildbucketResponse(
        'sm', 'sb')
    tryjob_b_run_1.created_time = datetime.datetime(2017, 1, 2, 0, 0, 0)
    tryjob_b_run_1.try_job_key = tryjob_b.key
    tryjob_b_run_1.put()
    tryjob_b.try_job_ids.append('tbr1')
    tryjob_b.put()

    self.assertEqual([(tryjob_a_run_1, tryjob_a_run_3), (tryjob_b_run_1, None)],
                     swarmbucket_performance._FindJobPairs([{
                         'try_job_data': tryjob_a_run_1,
                         'builder': 'sm/sb'
                     }, {
                         'try_job_data': tryjob_b_run_1,
                         'builder': 'sm/sb'
                     }], builders))

  def testGetBotFromBuildbucketReponse(self):
    self.assertEqual(
        'luci.chromium.mac/mac_variable',
        swarmbucket_performance._GetBotFromBuildbucketResponse({
            'bucket': 'luci.chromium.mac',
            'tags': ['nocolontag', 'builder:mac_variable', 'other:tag']
        }))
    self.assertIsNone(
        swarmbucket_performance._GetBotFromBuildbucketResponse({
            'bucket': 'luci.chromium.mac',
            'tags': ['other:tag']
        }))
    with self.assertRaises(Exception):
      swarmbucket_performance._GetBotFromBuildbucketResponse({
          'bucket': 'luci.chromium.mac'
      })

  @mock.patch.object(FinditConfig, 'builders_to_trybots', BUILDER_MAP)
  def testGetSwarmbucketBuilders(self):
    self.assertEqual({
        'luci.chromium/swarm_builder3': 'chromium/builder3'
    }, swarmbucket_performance._GetSwarmbucketBuilders())

  def testGetStartEndDates(self):
    # Normal
    start, end = swarmbucket_performance._GetStartEndDates(
        '2017-01-01', '2017-02-01')
    self.assertEqual(datetime.datetime(2017, 1, 1, 0, 0, 0), start)
    self.assertEqual(datetime.datetime(2017, 2, 1, 0, 0, 0), end)

    # Reversed
    start, end = swarmbucket_performance._GetStartEndDates(
        '2017-01-01', '2017-02-01')
    self.assertEqual(datetime.datetime(2017, 1, 1, 0, 0, 0), start)
    self.assertEqual(datetime.datetime(2017, 2, 1, 0, 0, 0), end)

    # The following sub cases should return the default (last 30 days)
    with mock.patch.object(
        time_util,
        "GetUTCNow",
        return_value=datetime.datetime(2017, 1, 31, 0, 0, 0)):
      # Bad format
      start, end = swarmbucket_performance._GetStartEndDates('2017-01-01', '1')
      self.assertEqual(datetime.datetime(2017, 1, 1, 0, 0, 0), start)
      self.assertEqual(datetime.datetime(2017, 1, 31, 0, 0, 0), end)

      # One date missing
      start, end = swarmbucket_performance._GetStartEndDates(None, '2017-01-01')
      self.assertEqual(datetime.datetime(2017, 1, 1, 0, 0, 0), start)
      self.assertEqual(datetime.datetime(2017, 1, 31, 0, 0, 0), end)

      # Neither date provided
      start, end = swarmbucket_performance._GetStartEndDates(None, None)
      self.assertEqual(datetime.datetime(2017, 1, 1, 0, 0, 0), start)
      self.assertEqual(datetime.datetime(2017, 1, 31, 0, 0, 0), end)

  @mock.patch.object(FinditConfig, 'builders_to_trybots', BUILDER_MAP)
  @mock.patch.object(
      swarmbucket_performance,
      "_GetStartEndDates",
      return_value=(datetime.datetime(2017, 1, 1, 0, 0, 0), datetime.datetime(
          2017, 1, 31, 0, 0, 0)))
  def testHandler(self, *_):

    def _addRun(try_job_entity,
                t_master,
                t_builder,
                run_id,
                created,
                start,
                end,
                error=False):
      base_time = datetime.datetime(2017, 1, 1, 0, 0, 0)
      run = WfTryJobData.Create(run_id)
      run.last_buildbucket_response = _GenFakeBuildbucketResponse(
          t_master, t_builder)
      run.created_time = base_time + datetime.timedelta(minutes=created)
      run.start_time = base_time + datetime.timedelta(minutes=start)
      run.end_time = base_time + datetime.timedelta(minutes=end)
      if error:
        run.error_code = 1
        run.error = 'Unknown error'
      run.try_job_key = try_job_entity.key
      run.try_job_url = 'https://fake.url/' + run_id
      run.put()
      try_job_entity.try_job_ids.append(run_id)
      try_job_entity.put()

    swarmbucket_no_buildbot = WfTryJob.Create('luci.chromium', 'swarm_builder3',
                                              1)
    _addRun(swarmbucket_no_buildbot, 'luci.chromium', 'swarm_builder3', 'sbr1',
            100, 110, 120)
    _addRun(swarmbucket_no_buildbot, 'luci.chromium', 'swarm_builder3', 'sbr2',
            100, 110, 120, True)

    swarmbucket_with_buildbot = WfTryJob.Create('luci.chromium',
                                                'swarm_builder3', 2)
    _addRun(swarmbucket_with_buildbot, 'luci.chromium', 'swarm_builder3',
            'bb_sbr1', 100, 110, 120)
    _addRun(swarmbucket_with_buildbot, 'chromium', 'builder3', 'bb_bbr1', 100,
            110, 120)
    _addRun(swarmbucket_with_buildbot, 'chromium', 'builder3', 'bb_bbr2', 100,
            110, 120, True)

    swarmbucket_failed_buildbot = WfTryJob.Create('luci.chromium',
                                                  'swarm_builder3', 3)
    _addRun(swarmbucket_failed_buildbot, 'luci.chromium', 'swarm_builder3',
            'bb2_sbr1', 100, 110, 120)
    _addRun(swarmbucket_failed_buildbot, 'chromium', 'builder3', 'bb2_bbr2',
            100, 110, 120, True)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get('/swarmbucket_performance?format=json')
    self.assertEqual({'jobs': [{
        "buildbot_try_job_id": "bb2_bbr2",
        "swarmbucket_builder": "luci.chromium/swarm_builder3",
        "buildbot_builder": "chromium/builder3",
        "swarmbucket_run_time": 600.0,
        "buildbot_completion_date": "2017-01-01 02:00:00 UTC",
        "swarmbucket_completion_date": "2017-01-01 02:00:00 UTC",
        "swarmbucket_try_job_url": "https://fake.url/bb2_sbr1",
        "buildbot_try_job_url": "https://fake.url/bb2_bbr2",
        "swarmbucket_try_job_id": "bb2_sbr1"
    }, {
        "buildbot_try_job_id": "bb_bbr1",
        "swarmbucket_builder": "luci.chromium/swarm_builder3",
        "buildbot_builder": "chromium/builder3",
        "swarmbucket_run_time": 600.0,
        "buildbot_completion_date": "2017-01-01 02:00:00 UTC",
        "swarmbucket_completion_date": "2017-01-01 02:00:00 UTC",
        "buildbot_run_time": 600.0,
        "buildbot_try_job_url": "https://fake.url/bb_bbr1",
        "swarmbucket_try_job_url": "https://fake.url/bb_sbr1",
        "swarmbucket_try_job_id": "bb_sbr1"
    }, {
        "swarmbucket_builder": "luci.chromium/swarm_builder3",
        "swarmbucket_completion_date": "2017-01-01 02:00:00 UTC",
        "swarmbucket_run_time": 600.0,
        "swarmbucket_try_job_id": "sbr1",
        "swarmbucket_try_job_url": "https://fake.url/sbr1"
    }, {
        "swarmbucket_builder": "luci.chromium/swarm_builder3",
        "swarmbucket_completion_date": "2017-01-01 02:00:00 UTC",
        "swarmbucket_try_job_id": "sbr2",
        "swarmbucket_try_job_url": "https://fake.url/sbr2"
    }]}, response.json_body)
    response = self.test_app.get('/swarmbucket_performance')
    self.assertEquals(200, response.status_int)
