# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

import webapp2

from common import constants
from handlers import check_reverted_cls
from infra_api_clients.codereview import cl_info
from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.rietveld import Rietveld
from libs import time_util
from model import revert_cl_status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util
from waterfall.test import wf_testcase

_MOCKED_FINDIT_REVERTING_CL = cl_info.ClInfo('codereview.chromium.org', '456')
_MOCKED_FINDIT_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 1, 10))
]
_MOCKED_FINDIT_REVERTING_CL.commit_attempts = {
    '1001':
        cl_info.CommitAttempt('1001', 'sheriff@chromium.org',
                              datetime(2017, 3, 15, 0, 7)),
}
_MOCKED_FINDIT_REVERTED_CL_INFO = cl_info.ClInfo('codereview.chromium.org',
                                                 '123')
_MOCKED_FINDIT_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)
]
_MOCKED_FINDIT_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_FINDIT_REVERTING_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))
]

_MOCKED_SHERIFF_REVERTING_CL = cl_info.ClInfo('codereview.chromium.org', '456')
_MOCKED_SHERIFF_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 0, 8))
]
_MOCKED_SHERIFF_REVERTING_CL.commit_attempts = {
    '1001':
        cl_info.CommitAttempt('1001', 'sheriff@chromium.org',
                              datetime(2017, 3, 15, 0, 7)),
}
_MOCKED_SHERIFF_REVERTED_CL_INFO = cl_info.ClInfo('codereview.chromium.org',
                                                  '123')
_MOCKED_SHERIFF_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)
]
_MOCKED_SHERIFF_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_SHERIFF_REVERTING_CL, 'sheriff@chromium.org',
                   datetime(2017, 3, 15, 1, 7)),
    cl_info.Revert('1000', _MOCKED_FINDIT_REVERTING_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))
]  # Findit slower.

_MOCKED_SHERIFF_FAST_REVERTING_CL = cl_info.ClInfo('codereview.chromium.org',
                                                   '456')
_MOCKED_SHERIFF_FAST_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 0, 8))
]
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO = cl_info.ClInfo(
    'codereview.chromium.org', '123')
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)
]
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_SHERIFF_REVERTING_CL, 'sheriff@chromium.org',
                   datetime(2017, 3, 15, 1, 7))
]

_MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL = cl_info.ClInfo(
    'codereview.chromium.org', '456')
_MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL.commits = []  # Never committed.
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO = cl_info.ClInfo(
    'codereview.chromium.org', '123')
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)
]
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))
]


class CheckRevertedCLsTest(wf_testcase.WaterfallTestCase):

  app_module = webapp2.WSGIApplication(
      [
          ('/check-reverted-cls', check_reverted_cls.CheckRevertedCLs),
      ],
      debug=True)

  def testUpdateSuspectedCLBailOut(self):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.sheriff_action_time = datetime(2017, 4, 6, 0, 0)
    check_reverted_cls._UpdateSuspectedCL(suspected_cl,
                                          datetime(2017, 4, 6, 0, 1))
    self.assertEqual(
        datetime(2017, 4, 6, 0, 0), suspected_cl.sheriff_action_time)

  def testCheckRevertStatusOfSuspectedCLNoRevert(self):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    self.assertEqual(
        (False, None, None),
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=None)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLRevertedNoCodeReview(self, mock_fn, _):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'badhost.org/123',
        'review_server_host': 'badhost.org/123',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    self.assertEqual(
        (None, None, None),
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(Rietveld, 'GetClDetails', return_value=None)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLNoClDetails(self, mock_fn, *_):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'badhost.org/123',
        'review_server_host': 'badhost.org/123',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    self.assertEqual(
        (None, 'https://codereview.chromium.org/123/', None),
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld,
      'GetClDetails',
      return_value=_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO)
  @mock.patch(
      'infra_api_clients.codereview.cl_info.ClInfo.GetRevertCLsByRevision',
      mock.Mock(return_value=None))
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLNoRevertCLsByRevision(self, mock_f, *_):
    mock_f.return_value = {
        'commit_position': 1,
        'code_review_url': 'badhost.org/123',
        'review_server_host': 'badhost.org/123',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    self.assertEqual(
        (None, 'https://codereview.chromium.org/123/', None),
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld, 'GetClDetails', return_value=_MOCKED_FINDIT_REVERTED_CL_INFO)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLReverted(self, mock_fn, *_):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'codereview.chromium.org/123',
        'review_server_host': 'codereview.chromium.org',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    result = check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)

    self.assertTrue(result[0])
    self.assertEqual(result[1], 'https://codereview.chromium.org/123/')
    self.assertEqual(result[2], revert_cl_status.COMMITTED)
    self.assertEqual(revert_cl_status.COMMITTED, suspected_cl.revert_cl.status)

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld, 'GetClDetails', return_value=_MOCKED_SHERIFF_REVERTED_CL_INFO)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLSheriffIgnored(self, mock_fn, *_):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'codereview.chromium.org/123',
        'review_server_host': 'codereview.chromium.org',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)

    self.assertEqual(revert_cl_status.DUPLICATE, suspected_cl.revert_cl.status)

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld,
      'GetClDetails',
      return_value=_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLSheriffMuchFaster(self, mock_fn, *_):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'codereview.chromium.org/123',
        'review_server_host': 'codereview.chromium.org',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)
    self.assertEqual(
        datetime(2017, 3, 15, 1, 7), suspected_cl.sheriff_action_time)

  @mock.patch.object(
      codereview_util,
      'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld,
      'GetClDetails',
      return_value=_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCheckRevertStatusOfSuspectedCLFalsePositive(self, mock_fn, *_):
    mock_fn.return_value = {
        'commit_position': 1,
        'code_review_url': 'codereview.chromium.org/123',
        'review_server_host': 'codereview.chromium.org',
        'review_change_id': '123'
    }
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)
    self.assertEqual(revert_cl_status.FALSE_POSITIVE,
                     suspected_cl.revert_cl.status)

  @mock.patch.object(
      check_reverted_cls,
      '_CheckRevertStatusOfSuspectedCL',
      return_value=(True, 'https://codereview.chromium.org/123/',
                    revert_cl_status.COMMITTED))
  def testGetRevertCLData(self, _):
    start_date = datetime(2017, 4, 4, 0, 0)
    end_date = datetime(2017, 4, 6, 0, 0)

    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.identified_time = start_date
    suspected_cl.cr_notification_time = datetime(2017, 4, 5, 0, 0)
    suspected_cl.put()

    self.assertEqual({
        'start_date':
            '2017-04-04 00:00:00 UTC',
        'end_date':
            '2017-04-06 00:00:00 UTC',
        'processed': [{
            'cr_notification_time': '2017-04-05 00:00:00 UTC',
            'outcome': 'committed',
            'url': 'https://codereview.chromium.org/123/',
        }],
        'undetermined': []
    }, check_reverted_cls._GetRevertCLData(start_date, end_date))

  @mock.patch.object(
      check_reverted_cls,
      '_CheckRevertStatusOfSuspectedCL',
      return_value=(None, 'https://codereview.chromium.org/123/', None))
  def testGetRevertCLDataFailedToDetermine(self, _):
    start_date = datetime(2017, 4, 4, 0, 0)
    end_date = datetime(2017, 4, 6, 0, 0)

    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.identified_time = start_date
    suspected_cl.cr_notification_time = datetime(2017, 4, 5, 0, 0)
    suspected_cl.put()

    self.assertEqual({
        'start_date':
            '2017-04-04 00:00:00 UTC',
        'end_date':
            '2017-04-06 00:00:00 UTC',
        'undetermined': [{
            'cr_notification_time': '2017-04-05 00:00:00 UTC',
            'url': 'https://codereview.chromium.org/123/',
            'outcome': None,
        }],
        'processed': []
    }, check_reverted_cls._GetRevertCLData(start_date, end_date))

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime(2017, 4, 16, 0, 0, 0))
  def testGetNoStartEndDates(self, _):
    response = self.test_app.get(
        '/check-reverted-cls',
        params={'format': 'json'},
        headers={'X-AppEngine-Cron': 'true'},
    )
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'start_date': '2017-04-14 00:00:00 UTC',
        'end_date': '2017-04-15 00:00:00 UTC',
        'processed': [],
        'undetermined': []
    }

    self.assertEquals(expected_response, response.json_body)

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime(2017, 4, 16, 0, 0, 0))
  @mock.patch.object(
      check_reverted_cls,
      '_GetRevertCLData',
      return_value={
          'start_date':
              '2017-04-08 00:00:00 UTC',
          'end_date':
              '2017-04-16 00:00:00 UTC',
          'processed': [{
              'cr_notification_time': '2017-04-15 00:00:01 UTC',
              'outcome': 'reverted',
              'url': 'url'
          }],
          'undetermined': []
      })

  def testGet(self, *_):
    response = self.test_app.get(
        '/check-reverted-cls?start_date=2017-04-08&end_date=2017-04-16',
        params={'format': 'json'},
        headers={'X-AppEngine-Cron': 'true'},
    )
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'start_date':
            '2017-04-08 00:00:00 UTC',
        'end_date':
            '2017-04-16 00:00:00 UTC',
        'processed': [{
            'cr_notification_time': '2017-04-15 00:00:01 UTC',
            'outcome': 'reverted',
            'url': 'url'
        }],
        'undetermined': []
    }

    self.assertEquals(expected_response, response.json_body)
