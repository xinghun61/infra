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
from model.wf_suspected_cl import WfSuspectedCL
from services import gerrit

_IRC_HOST = 'irc.freenode.net'
_IRC_CHANNEL = '#chromium'
_IRC_NICK = 'Findit'
_IRC_DISC = 'CulpritFinder'


def _GenerateMessage(revert_cl_url, commit_position, revision, culprit_key,
                     submitted):
  action = 'submitted' if submitted else 'created'
  return textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) has %s a revert (%s) for CL %s,
      because it was identified as the culprit for failures in the build
      cycles as shown on:
      https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
      action, revert_cl_url, commit_position or revision, culprit_key)


def SendMessageToIrc(pipeline_input):
  repo_name = pipeline_input.cl_key.repo_name
  revision = pipeline_input.cl_key.revision
  revert_status = pipeline_input.revert_status
  submitted = pipeline_input.submitted

  if revert_status != gerrit.CREATED_BY_FINDIT:
    # No need to send notification to irc if Findit doesn't create revert.
    return False

  culprit = WfSuspectedCL.Get(repo_name, revision)
  if not culprit:
    logging.error('Failed to send notification to irc about culprit %s, %s:'
                  ' entity not found in datastore.' % (repo_name, revision))
    return False

  revert_cl_url = culprit.revert_cl_url
  if not revert_cl_url:
    logging.error('Failed to send notification to irc about culprit %s, %s:'
                  ' revert CL url not found.' % (repo_name, revision))
    return False

  message = _GenerateMessage(revert_cl_url, culprit.commit_position, revision,
                             culprit.key.urlsafe(), submitted)

  try:
    with IRCClient(_IRC_HOST, _IRC_CHANNEL, _IRC_NICK, _IRC_DISC) as i:
      i.SendMessage(message)
      return True
  # This is just in case any exception happens when sending message.
  except Exception, e:
    logging.error('Sending message to IRC failed with %s.' % e)
    return False
