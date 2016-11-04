# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from issue_tracker import IssueTrackerAPI

from common.pipeline_wrapper import BasePipeline


def _GetIssue(bug_id, issue_tracker):
  """Returns the issue of the given bug.

  Traverse if the bug was merged into another."""
  issue = issue_tracker.getIssue(bug_id)
  while issue and issue.merged_into:
    issue = issue_tracker.getIssue(issue.merged_into)
  return issue


class PostCommentToBugPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, bug_id, comment, labels, project_name='chromium'):
    """Posts a comment and adds labels to the bug.

    Args:
      bug_id (int): The bug id to update.
      comment (str): The comment to post.
      labels (list): A list labels to add.
      project_name (str): The project name for the bug. Default to 'chromium'.
    """
    assert bug_id, 'Invalid bug id: %s' % bug_id

    issue_tracker = IssueTrackerAPI(project_name)
    issue = _GetIssue(bug_id, issue_tracker)
    if not issue:
      logging.warn('Bug %s/%s or the merged-into one seems deleted!',
                   project_name, bug_id)
      return

    for label in labels:
      issue.labels.append(label)

    issue_tracker.update(issue, comment, send_email=True)
    logging.info('Bug %s/%s was updated.', project_name, bug_id)
