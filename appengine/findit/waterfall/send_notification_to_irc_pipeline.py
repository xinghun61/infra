# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import textwrap

from gae_libs.pipeline_wrapper import BasePipeline
from libs.irc_client import IRCClient
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import create_revert_cl_pipeline


_IRC_HOST = 'irc.freenode.net'
_IRC_CHANNEL = '#chromium'
_IRC_NICK = 'Findit'
_IRC_DISC = 'CulpritFinder'


def _GenerateMessage(revert_cl_url, commit_position, revision, culprit_key):
  return textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) has created a revert (%s) for CL %s,
      because it was identified as the culprit for failures in the build
      cycles as shown on:
      https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
      revert_cl_url, commit_position or revision, culprit_key)


class SendNotificationToIrcPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, repo_name, revision, revert_status):
    if revert_status != create_revert_cl_pipeline.CREATED_BY_FINDIT:
      # No need to send notification to irc if Findit doesn't create revert.
      return

    culprit = WfSuspectedCL.Get(repo_name, revision)
    if not culprit:
      logging.error('Failed to send notification to irc about culprit %s, %s:'
                    ' entity not found in datastore.' % (repo_name, revision))
      return

    revert_cl_url = culprit.revert_cl_url
    if not revert_cl_url:
      logging.error('Failed to send notification to irc about culprit %s, %s:'
                    ' revert CL url not found.' % (repo_name, revision))
      return

    message = _GenerateMessage(
        revert_cl_url, culprit.commit_position, revision,
        culprit.key.urlsafe())

    try:
      with IRCClient(_IRC_HOST, _IRC_CHANNEL, _IRC_NICK, _IRC_DISC) as i:
        i.SendMessage(message)
    # This is just in case any exception happens when sending message.
    except Exception, e:
        logging.error('Sending message to IRC failed with %s.' % e)
