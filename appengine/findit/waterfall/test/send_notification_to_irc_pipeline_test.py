# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import textwrap

from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import create_revert_cl_pipeline
from waterfall import send_notification_to_irc_pipeline
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.test import wf_testcase


class SendNotificationToIrcPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(send_notification_to_irc_pipeline, 'IRCClient')
  def testNoNeedToSendNotification(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = create_revert_cl_pipeline.CREATED_BY_SHERIFF
    pipeline = SendNotificationToIrcPipeline()
    pipeline.run(repo_name, revision, revert_status)

    mocked_irc.assert_not_called()

  @mock.patch.object(send_notification_to_irc_pipeline, 'IRCClient')
  def testSendNotificationNoCulprit(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = create_revert_cl_pipeline.CREATED_BY_FINDIT
    pipeline = SendNotificationToIrcPipeline()
    pipeline.run(repo_name, revision, revert_status)

    mocked_irc.assert_not_called()

  @mock.patch.object(send_notification_to_irc_pipeline, 'IRCClient')
  def testSendNotificationNoRevert(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = create_revert_cl_pipeline.CREATED_BY_FINDIT
    WfSuspectedCL.Create(repo_name, revision, 1).put()
    pipeline = SendNotificationToIrcPipeline()
    pipeline.run(repo_name, revision, revert_status)

    mocked_irc.assert_not_called()

  @mock.patch.object(logging, 'info')
  def testSendNotification(self, mocked_logging):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = create_revert_cl_pipeline.CREATED_BY_FINDIT

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    class MockedIRCClient(object):
      def __init__(self, *_):
        pass

      def __enter__(self):
        return self

      def __exit__(self, *_):
        pass

      def SendMessage(self, message):
        logging.info(message)

    self.mock(send_notification_to_irc_pipeline, 'IRCClient', MockedIRCClient)

    pipeline = SendNotificationToIrcPipeline()
    pipeline.run(repo_name, revision, revert_status)

    expected_message = send_notification_to_irc_pipeline._GenerateMessage(
        culprit.revert_cl_url, culprit.commit_position, revision,
        culprit.key.urlsafe())
    mocked_logging.assert_called_with(expected_message)

  @mock.patch.object(logging, 'error')
  def testSendNotificationException(self, mocked_logging):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = create_revert_cl_pipeline.CREATED_BY_FINDIT

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    class MockedIRCClient(object):
      def __init__(self, *_):
        pass

      def __enter__(self):
        return self

      def __exit__(self, *_):
        pass

      def SendMessage(self, _):
        raise Exception('An exception')

    self.mock(send_notification_to_irc_pipeline, 'IRCClient', MockedIRCClient)

    pipeline = SendNotificationToIrcPipeline()
    pipeline.run(repo_name, revision, revert_status)

    expected_message = 'Sending message to IRC failed with An exception.'
    mocked_logging.assert_called_with(expected_message)

  def testGenerateMessage(self):
    revert_cl_url = 'revert_cl_url'
    commit_position = 'commit_position'
    culprit_key = 'culprit_key'

    expected_message = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) has created a revert (%s) for CL %s,
        because it was identified as the culprit for failures in the build
        cycles as shown on:
        https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
        revert_cl_url, commit_position, culprit_key)

    self.assertEqual(expected_message,
                     send_notification_to_irc_pipeline._GenerateMessage(
                         revert_cl_url, commit_position, None, culprit_key))