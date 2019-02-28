# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for irc-related operations.

It provides functions to:
  * send notification to irc.
"""

import logging
import textwrap

from libs.irc_client import IRCClient
from services import constants

_IRC_HOST = 'irc.freenode.net'
_IRC_CHANNEL = '#chromium'
_IRC_NICK = 'Findit'
_IRC_DISC = 'CulpritFinder'


def _GenerateMessage(revert_cl_url, commit_position, revision, culprit_key,
                     commit_status):
  action = 'submitted' if commit_status == constants.COMMITTED else 'created'
  return textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) has %s a revert (%s) for CL %s,
      because it was identified as the culprit for failures in the build
      cycles as shown on:
      https://analysis.chromium.org/waterfall/culprit?key=%s""") % (
      action, revert_cl_url, commit_position or revision, culprit_key)


def SendMessageToIrc(revert_cl_url, commit_position, revision, culprit_key,
                     commit_status):

  message = _GenerateMessage(revert_cl_url, commit_position, revision,
                             culprit_key, commit_status)

  try:
    with IRCClient(_IRC_HOST, _IRC_CHANNEL, _IRC_NICK, _IRC_DISC) as i:
      i.SendMessage(message)
      return True
  # This is just in case any exception happens when sending message.
  except Exception, e:
    logging.error('Sending message to IRC failed with %s.' % e)
    return False
