# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import textwrap

from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from services import constants
from services import irc
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

  def testSendNotification(self):
    repo_name = 'chromium'
    revision = 'rev'
    commit_position = 123
    revert_cl_url = 'revert_url'
    commit_status = constants.SKIPPED

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.put()

    self.mock(irc, 'IRCClient', MockedIRCClient)
    self.assertTrue(
        irc.SendMessageToIrc(revert_cl_url, commit_position, revision,
                             culprit.key.urlsafe(), commit_status))

  @mock.patch.object(irc, '_GenerateMessage', return_value='exception')
  @mock.patch.object(logging, 'error')
  def testSendNotificationException(self, mocked_logging, _):
    repo_name = 'chromium'
    revision = 'rev'
    commit_position = 123
    revert_cl_url = 'revert_url'
    commit_status = constants.SKIPPED

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.put()

    self.mock(irc, 'IRCClient', MockedIRCClient)
    self.assertFalse(
        irc.SendMessageToIrc(revert_cl_url, commit_position, revision,
                             culprit.key.urlsafe(), commit_status))

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
        https://analysis.chromium.org/waterfall/culprit?key=%s""") % (
        revert_cl_url, commit_position, culprit_key)

    self.assertEqual(
        expected_message,
        irc._GenerateMessage(revert_cl_url, commit_position, None, culprit_key,
                             constants.ERROR))
