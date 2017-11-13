# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import textwrap

from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationToIrcPipelineInput)
from services import irc
from services import gerrit
from waterfall.test import wf_testcase


class MockedIRCClient(object):

  def __init__(self, *_):
    pass

  def __enter__(self):
    return self

  def __exit__(self, *_):
    pass

  def SendMessage(self, message):
    if message == 'exception':
      raise Exception('An exception')
    else:
      logging.info(message)


class IrcTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(irc, 'IRCClient')
  def testNoNeedToSendNotification(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_SHERIFF
    submitted = False
    pipeline_input = SendNotificationToIrcPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        submitted=submitted)
    self.assertFalse(irc.SendMessageToIrc(pipeline_input))
    mocked_irc.assert_not_called()

  @mock.patch.object(irc, 'IRCClient')
  def testSendNotificationNoCulprit(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    submitted = False
    pipeline_input = SendNotificationToIrcPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        submitted=submitted)
    self.assertFalse(irc.SendMessageToIrc(pipeline_input))

    mocked_irc.assert_not_called()

  @mock.patch.object(irc, 'IRCClient')
  def testSendNotificationNoRevert(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    submitted = False

    WfSuspectedCL.Create(repo_name, revision, 1).put()

    pipeline_input = SendNotificationToIrcPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        submitted=submitted)
    self.assertFalse(irc.SendMessageToIrc(pipeline_input))

    mocked_irc.assert_not_called()

  def testSendNotification(self):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    submitted = False

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    self.mock(irc, 'IRCClient', MockedIRCClient)

    pipeline_input = SendNotificationToIrcPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        submitted=submitted)
    self.assertTrue(irc.SendMessageToIrc(pipeline_input))

  @mock.patch.object(irc, '_GenerateMessage', return_value='exception')
  @mock.patch.object(logging, 'error')
  def testSendNotificationException(self, mocked_logging, _):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    submitted = False

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    self.mock(irc, 'IRCClient', MockedIRCClient)

    pipeline_input = SendNotificationToIrcPipelineInput(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        submitted=submitted)
    self.assertFalse(irc.SendMessageToIrc(pipeline_input))

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
                     irc._GenerateMessage(revert_cl_url, commit_position, None,
                                          culprit_key, False))
