# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging

from google.appengine.ext import ndb

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from infra_api_clients.codereview import codereview_util
from libs import time_util
from model import revert_cl_status
from model.wf_config import FinditConfig
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util

# Check 1 day at a time if run as a cron-job.
_DAYS_TO_CHECK = 1
_DEFAULT_PAGE_SIZE = 1000


@ndb.transactional
def _UpdateSuspectedCL(suspected_cl,
                       sheriff_action_time=None,
                       revert_commit_timestamp=None,
                       revert_status=None,
                       overwrite=False):
  """Updates a suspected cl based on revert cl results.

  Args:
    suspected_cl (WfSuspectedCL): The suspected cl entity to update.
    sheriff_action_time (datetime): The timestamp a sheriff took action on a
        culprit.
    revert_commit_timestamp (datetime): The timestamp a Findit-created revert cl
        was committed.
    revert_status (int): The eventual status code of a Findit-created revert cl.
    overwrite (bool): Whether or not to overwrite the existing timestamp.
  """
  if suspected_cl.sheriff_action_time and not overwrite:
    # Bail out if this suspected CL has already been processed.
    return

  suspected_cl.sheriff_action_time = (suspected_cl.sheriff_action_time or
                                      sheriff_action_time)

  if suspected_cl.revert_cl:
    suspected_cl.revert_cl.committed_time = (
        suspected_cl.revert_cl.committed_time or revert_commit_timestamp)
    suspected_cl.revert_cl.status = (suspected_cl.revert_cl.status or
                                     revert_status)

  suspected_cl.put()


def _CheckRevertStatusOfSuspectedCL(suspected_cl):
  """Updates suspected_cl with findings about what happened to its revert CL.

  Args:
    suspected_cl (wf_suspected_cl): A WfSuspectedCL entity.

  Returns:
    processed (bool): True if the suspected cl's revert outcome was determined,
      False if reverting was not relevant. None if the cl needed reverting but
      an outcome could not be determined.
    url (str): The code review url for manual investigation.
    status (str): The eventual outcome of the revert cl.
  """
  revert_cl = suspected_cl.revert_cl

  if not revert_cl and not suspected_cl.should_be_reverted:
    # Findit did not deem this suspected cl as needing revert. No action needed.
    return False, None, None

  repo = suspected_cl.repo_name
  revision = suspected_cl.revision
  culprit_info = suspected_cl_util.GetCulpritInfo(repo, revision)
  review_server_host = culprit_info.get('review_server_host')
  change_id = culprit_info.get('review_change_id')

  if not review_server_host or not change_id:  # pragma: no cover
    # TODO(lijeffrey): Handle cases a patch was committed without review.
    return None, None, None

  code_review_settings = FinditConfig().Get().code_review_settings
  codereview = codereview_util.GetCodeReviewForReview(review_server_host,
                                                      code_review_settings)
  if not codereview:
    logging.error('Could not get codereview for %s/q/%s', review_server_host,
                  change_id)
    return None, None, None

  cl_info = codereview.GetClDetails(change_id)
  code_review_url = codereview.GetCodeReviewUrl(change_id)

  if not cl_info:
    logging.error('Could not get CL details for %s/q/%s', review_server_host,
                  change_id)
    return None, code_review_url, None
  reverts_to_check = cl_info.GetRevertCLsByRevision(revision)

  if not reverts_to_check:
    logging.error('Could not get revert info for %s/q/%s', review_server_host,
                  change_id)
    return None, code_review_url, None

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
          cq_attempt = revert.reverting_cl.commit_attempts[
              revert_commit.patchset_id]
          _UpdateSuspectedCL(
              suspected_cl,
              sheriff_action_time=cq_attempt.last_cq_timestamp,
              revert_commit_timestamp=revert_commit.timestamp,
              revert_status=revert_cl_status.COMMITTED)
          break
        else:
          # Sheriff used own revert CL.
          _UpdateSuspectedCL(
              suspected_cl,
              sheriff_action_time=revert_commit.timestamp,
              revert_status=revert_cl_status.DUPLICATE)
          break

    # No revert was ever committed. False positive.
    if not any_revert_committed:
      # TODO(crbug.com/702056): Close the revert CLs that were not used.
      _UpdateSuspectedCL(
          suspected_cl, revert_status=revert_cl_status.FALSE_POSITIVE)

  elif suspected_cl.should_be_reverted:  # pragma: no branch
    # Findit could have created a revert CL, but the sheriff was too fast.
    # Find the first revert that was successfully landed.
    for revert in reverts_to_check:  # pragma: no branch
      revert_commits = revert.reverting_cl.commits
      if revert_commits:  # pragma: no branch
        _UpdateSuspectedCL(suspected_cl, sheriff_action_time=revert.timestamp)
        break

  return True, code_review_url, (revert_cl.status
                                 if revert_cl else revert_cl_status.DUPLICATE)


def _GetRevertCLData(start_date, end_date):
  data = {
      'start_date': time_util.FormatDatetime(start_date),
      'end_date': time_util.FormatDatetime(end_date),
      'processed': [],
      'undetermined': []
  }

  query = WfSuspectedCL.query(WfSuspectedCL.identified_time >= start_date,
                              WfSuspectedCL.identified_time < end_date)

  more = True
  cursor = None
  all_suspected_cls = []
  while more:
    suspected_cls, cursor, more = query.fetch_page(
        _DEFAULT_PAGE_SIZE, start_cursor=cursor)
    all_suspected_cls.extend(suspected_cls)

  for suspected_cl in all_suspected_cls:
    processed, review_url, outcome = _CheckRevertStatusOfSuspectedCL(
        suspected_cl)

    result = {
        'cr_notification_time':
            time_util.FormatDatetime(suspected_cl.cr_notification_time or
                                     suspected_cl.updated_time),
        'outcome':
            revert_cl_status.STATUS_TO_DESCRIPTION.get(outcome),
        'url':
            review_url,
    }

    if processed:
      data['processed'].append(result)
    elif processed is None:  # pragma: no branch
      data['undetermined'].append(result)

  return data


class CheckRevertedCLs(BaseHandler):
  """Checks the final outcome of suspected CLs Findit identified to revert."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    start = self.request.get('start_date')
    end = self.request.get('end_date')

    if not start and not end:
      midnight_today = time_util.GetMostRecentUTCMidnight()
      end_date = midnight_today - timedelta(days=1)
      start_date = end_date - timedelta(days=_DAYS_TO_CHECK)
    else:
      # Manually accessed the page with a specific date range to process.
      start_date, end_date = time_util.GetStartEndDates(start, end)

    return {
        'template': 'check_reverted_cls.html',
        'data': _GetRevertCLData(start_date, end_date)
    }
