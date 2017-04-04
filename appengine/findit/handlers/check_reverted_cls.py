# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta
import logging

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from infra_api_clients.codereview import codereview_util
from libs import time_util
from model import revert_cl_status
from model.wf_config import FinditConfig
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util


# Check 1 day at a time.
_DAYS_TO_CHECK = 1


def _CheckRevertStatusOfSuspectedCL(suspected_cl):
  """Updates suspected_cl with findings about what happened to its revert CL.

  Args:
    suspected_cl (wf_suspected_cl): A WfSuspectedCL entity.

  Returns:
    bool: True if the entity was successfully updated, False if no updates were
        needed, and None if no update could be determined.
  """
  revert_cl = suspected_cl.revert_cl

  if not revert_cl and not suspected_cl.should_be_reverted:
    # Findit did not deem this suspected cl as needing revert. No action needed.
    return False

  repo = suspected_cl.repo_name
  revision = suspected_cl.revision
  culprit_info = suspected_cl_util.GetCulpritInfo(repo, revision)
  review_server_host = culprit_info.get('review_server_host')
  change_id = culprit_info.get('review_change_id')

  if not review_server_host or not change_id:  # pragma: no cover
    # TODO(lijeffrey): Handle cases a patch was committed without review.
    return None

  code_review_settings = FinditConfig().Get().code_review_settings
  codereview = codereview_util.GetCodeReviewForReview(
      review_server_host, code_review_settings)
  if not codereview:
    logging.error('Could not get codereview for %s/q/%s' % (
        review_server_host, change_id))
    return None

  cl_info = codereview.GetClDetails(change_id)

  if not cl_info:
    logging.error('Could not get CL details for %s/q/%s' % (
        review_server_host, change_id))
    return None
  reverts_to_check = cl_info.GetRevertCLsByRevision(revision)

  if not reverts_to_check:
    logging.error('Could not get revert info for %s/q/%s' % (
        review_server_host, change_id))
    return None

  reverts_to_check.sort(key=lambda x: x.timestamp)

  if revert_cl:  # Findit attempted to create a revert cl.
    any_revert_committed = False
    # Check whose revert CL was first commited.
    for revert in reverts_to_check:  # pragma: no branch
      reverting_user = revert.reverting_user_email
      revert_commits = revert.reverting_cl.commits

      if revert_commits:  # pragma: no branch
        any_revert_committed = True
        revert_commit = revert_commits[0]

        if reverting_user == constants.DEFAULT_SERVICE_ACCOUNT:
          # The sheriff used Findit's reverting CL.
          revert_cl.committed_time = revert_commit.timestamp
          revert_cl.status = revert_cl_status.COMMITTED
          cq_attempt = revert.reverting_cl.commit_attempts[
              revert_commit.patchset_id]
          suspected_cl.sheriff_action_time = cq_attempt.last_cq_timestamp
          suspected_cl.put()
          break
        else:
          # Sheriff used own revert CL.
          revert_cl.status = revert_cl_status.DUPLICATE
          suspected_cl.sheriff_action_time = revert_commit.timestamp
          suspected_cl.put()
          break

    # No revert was ever committed. False positive.
    if not any_revert_committed:
      # TODO(crbug.com/702056): Close the revert CLs that were not used.
      revert_cl.status = revert_cl_status.FALSE_POSITIVE
      suspected_cl.put()

  elif suspected_cl.should_be_reverted:  # pragma: no branch
    # Findit could have created a revert CL, but the sheriff was too fast.
    # Find the first revert that was successfully landed.
    for revert in reverts_to_check:  # pragma: no branch
      revert_commits = revert.reverting_cl.commits
      if revert_commits:  # pragma: no branch
        suspected_cl.sheriff_action_time = revert.timestamp
        suspected_cl.put()
        break

  return True


class CheckRevertedCLs(BaseHandler):
  """Checks the final outcome of suspected CLs Findit identified to revert."""

  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):  # pragma: no cover
    midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)

    # Skip 1 day to ensure a CL's results are unlikely still in flux.
    end_date = midnight_today - timedelta(days=1)
    start_date = end_date - timedelta(days=_DAYS_TO_CHECK)

    suspected_cls = WfSuspectedCL.query(
        WfSuspectedCL.identified_time >= start_date,
        WfSuspectedCL.identified_time < end_date)

    for suspected_cl in suspected_cls:
      _CheckRevertStatusOfSuspectedCL(suspected_cl)
