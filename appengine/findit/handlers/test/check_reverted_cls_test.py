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
from model import revert_cl_status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util
from waterfall.test import wf_testcase


_MOCKED_FINDIT_REVERTING_CL = cl_info.ClInfo('codereview.chromium.org', '456')
_MOCKED_FINDIT_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 1, 10))]
_MOCKED_FINDIT_REVERTING_CL.commit_attempts = {
    '1001': cl_info.CommitAttempt(
        '1001', 'sheriff@chromium.org', datetime(2017, 3, 15, 0, 7)),
}
_MOCKED_FINDIT_REVERTED_CL_INFO = cl_info.ClInfo('codereview.chromium.org',
                                                 '123')
_MOCKED_FINDIT_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)]
_MOCKED_FINDIT_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_FINDIT_REVERTING_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))]

_MOCKED_SHERIFF_REVERTING_CL = cl_info.ClInfo(
    'codereview.chromium.org', '456')
_MOCKED_SHERIFF_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 0, 8))]
_MOCKED_SHERIFF_REVERTING_CL.commit_attempts = {
    '1001': cl_info.CommitAttempt(
        '1001', 'sheriff@chromium.org', datetime(2017, 3, 15, 0, 7)),
}
_MOCKED_SHERIFF_REVERTED_CL_INFO = cl_info.ClInfo('codereview.chromium.org',
                                                  '123')
_MOCKED_SHERIFF_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)]
_MOCKED_SHERIFF_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_SHERIFF_REVERTING_CL,
                   'sheriff@chromium.org',
                   datetime(2017, 3, 15, 1, 7)),
    cl_info.Revert('1000', _MOCKED_FINDIT_REVERTING_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))]  # Findit slower.

_MOCKED_SHERIFF_FAST_REVERTING_CL = cl_info.ClInfo(
    'codereview.chromium.org', '456')
_MOCKED_SHERIFF_FAST_REVERTING_CL.commits = [
    cl_info.Commit('1001', 'e5f6a7b8', datetime(2017, 3, 15, 0, 8))]
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO = cl_info.ClInfo(
    'codereview.chromium.org', '123')
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)]
_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_SHERIFF_REVERTING_CL,
                   'sheriff@chromium.org',
                   datetime(2017, 3, 15, 1, 7))]

_MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL = cl_info.ClInfo(
    'codereview.chromium.org', '456')
_MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL.commits = []  # Never committed.
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO = cl_info.ClInfo(
    'codereview.chromium.org', '123')
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO.commits = [
    cl_info.Commit('1000', 'a1b2c3d4', 1)]
_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO.reverts = [
    cl_info.Revert('1000', _MOCKED_FINDIT_FALSE_POSITIVE_REVERT_CL,
                   constants.DEFAULT_SERVICE_ACCOUNT,
                   datetime(2017, 3, 15, 1, 9))]


class CheckRevertedCLsTest(wf_testcase.WaterfallTestCase):

  app_module = webapp2.WSGIApplication([
      ('/check-reverted-cls',
       check_reverted_cls.CheckRevertedCLs),
  ], debug=True)

  def testCheckRevertStatusOfSuspectedCLNoRevert(self):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    self.assertFalse(
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'badhost.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=None)
  def testCheckRevertStatusOfSuspectedCLRevertedNoCodeReview(
      self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    self.assertFalse(
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(Rietveld, 'GetClDetails', return_value=None)
  def testCheckRevertStatusOfSuspectedCLNoClDetails(self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    self.assertIsNone(
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld, 'GetClDetails',
      return_value=_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO)
  @mock.patch(
      'infra_api_clients.codereview.cl_info.ClInfo.GetRevertCLsByRevision',
      mock.Mock(return_value=None))
  def testCheckRevertStatusOfSuspectedCLNoRevertCLsByRevision(self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    self.assertIsNone(
        check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl))

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=Rietveld(
          'codereview.chromium.org'))
  @mock.patch.object(Rietveld, 'GetClDetails',
                     return_value=_MOCKED_FINDIT_REVERTED_CL_INFO)
  def testCheckRevertStatusOfSuspectedCLReverted(
      self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)

    self.assertEqual(
        revert_cl_status.COMMITTED, suspected_cl.revert_cl.status)

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=Rietveld(
          'codereview.chromium.org'))
  @mock.patch.object(Rietveld, 'GetClDetails',
                     return_value=_MOCKED_SHERIFF_REVERTED_CL_INFO)
  def testCheckRevertStatusOfSuspectedCLSheriffIgnored(
      self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)

    self.assertEqual(
        revert_cl_status.DUPLICATE, suspected_cl.revert_cl.status)

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview',
      return_value=Rietveld('codereview.chromium.org'))
  @mock.patch.object(
      Rietveld, 'GetClDetails',
      return_value=_MOCKED_SHERIFF_FAST_REVERTED_CL_INFO)
  def testCheckRevertStatusOfSuspectedCLSheriffMuchFaster(self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.should_be_reverted = True

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)
    self.assertEqual(
        datetime(2017, 3, 15, 1, 7),
        suspected_cl.sheriff_action_time)

  @mock.patch.object(
      suspected_cl_util, 'GetCulpritInfo',
      return_value=(1, 'codereview.chromium.org/123', '123'))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=Rietveld(
          'codereview.chromium.org'))
  @mock.patch.object(Rietveld, 'GetClDetails',
                     return_value=_MOCKED_FINDIT_FALSE_POSITIVE_CL_INFO)
  def testCheckRevertStatusOfSuspectedCLFalsePositive(self, *_):
    suspected_cl = WfSuspectedCL.Create('chromium', 'a1b2c3d4', 1)
    suspected_cl.revert_cl = RevertCL()

    check_reverted_cls._CheckRevertStatusOfSuspectedCL(suspected_cl)
    self.assertEqual(
        revert_cl_status.FALSE_POSITIVE,
        suspected_cl.revert_cl.status)
