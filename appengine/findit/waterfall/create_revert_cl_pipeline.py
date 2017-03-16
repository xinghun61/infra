# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import textwrap

from google.appengine.ext import ndb

from common import constants
from common import rotations
from common.pipeline_wrapper import BasePipeline
from infra_api_clients.codereview import codereview_util
from libs import time_util
from model import analysis_status as status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util
from waterfall import waterfall_config


CREATED_BY_FINDIT = 0
CREATED_BY_SHERIFF = 1
ERROR = 2


@ndb.transactional
def _UpdateCulprit(
    repo_name, revision, revert_status=None, revert_cl=None):
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  culprit.should_be_reverted = True

  culprit.revert_status = revert_status or culprit.revert_status
  culprit.revert_cl = revert_cl or culprit.revert_cl

  if revert_cl:
    culprit.cr_notification_status = status.COMPLETED
    culprit.cr_notification_time = time_util.GetUTCNow()
  culprit.put()
  return culprit


def _RevertCulprit(repo_name, revision):

  culprit = _UpdateCulprit(repo_name, revision)

  if culprit.revert_cl and culprit.revert_status == status.COMPLETED:
    return CREATED_BY_FINDIT

  # 0. Gets information about this culprit.
  culprit_commit_position, culprit_code_review_url = (
      suspected_cl_util.GetCulpritInfo(repo_name, revision))

  codereview = codereview_util.GetCodeReviewForReview(culprit_code_review_url)
  culprit_change_id = codereview_util.GetChangeIdForReview(
    culprit_code_review_url)

  if not codereview or not culprit_change_id:  # pragma: no cover
    logging.error('Failed to get change id for %s/%s' % (repo_name, revision))
    return ERROR

  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  if not culprit_cl_info:  # pragma: no cover
    logging.error('Failed to get cl_info for %s/%s' % (repo_name, revision))
    return ERROR

  # 1. Checks if a revert CL by sheriff has been created.
  reverts = culprit_cl_info.GetRevertCLsByRevision(revision)

  if reverts is None:  # pragma: no cover
    # if no reverts, reverts should be [], only when some error happens it will
    # be None.
    logging.error('Failed to find patchset_id for %s/%s' % (
        repo_name, revision))
    return ERROR

  findit_revert = None
  for revert in reverts:
    if revert.reverting_user_email == constants.DEFAULT_SERVICE_ACCOUNT:
      findit_revert = revert
      break

  if reverts and not findit_revert:
    # Sheriff(s) created the revert CL(s).
    return CREATED_BY_SHERIFF

  # 2. Reverts the culprit.
  revert_change_id = codereview_util.GetChangeIdForReview(
      findit_revert.reverting_cl.url) if findit_revert else None

  # TODO (chanli): Better handle cases where 2 analyses are trying to revert
  # at the same time.
  if not revert_change_id:
    _UpdateCulprit(repo_name, revision, status.RUNNING)
    revert_reason = textwrap.dedent("""
        Findit identified CL at revision %s as the culprit for
        failures in the build cycles as shown on:
        https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
            culprit_commit_position or revision, culprit.key.urlsafe())

    revert_change_id = codereview.CreateRevert(
      revert_reason, culprit_change_id,
      culprit_cl_info.GetPatchsetIdByRevision(revision))

    if not revert_change_id:  # pragma: no cover
      _UpdateCulprit(repo_name, revision, status.ERROR)
      logging.error('Revert for culprit %s/%s failed.' % (repo_name, revision))
      culprit.put()
      return ERROR

  # Save revert CL info and notification info to culprit.
  if not culprit.revert_cl:
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = codereview.GetCodeReviewUrl(revert_change_id)
    revert_cl.created_time = time_util.GetUTCNow()
    _UpdateCulprit(repo_name, revision, None, revert_cl=revert_cl)

  # 3. Add reviewers.
  sheriffs = rotations.current_sheriffs()
  message = textwrap.dedent("""
    We find you currently are Chrome sheriff, could you review this revert CL
    which should fix failures in the build cycles as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
        culprit.key.urlsafe())
  success = codereview.AddReviewers(revert_change_id, sheriffs, message)

  if not success:  # pragma: no cover
    _UpdateCulprit(repo_name, revision, status.ERROR)
    logging.error('Failed to add reviewers for revert of culprit %s/%s' % (
      repo_name, revision))
    return ERROR

  _UpdateCulprit(repo_name, revision, revert_status=status.COMPLETED)
  return CREATED_BY_FINDIT


class CreateRevertCLPipeline(BasePipeline):
  def __init__(self, repo_name, revision):
    super(CreateRevertCLPipeline, self).__init__(repo_name, revision)
    self.repo_name = repo_name
    self.revision = revision

  def _LogUnexpectedAborting(self, was_aborted):
    if not was_aborted:  # pragma: no cover
      return

    culprit = WfSuspectedCL.Get(
        self.repo_name, self.revision)

    if culprit.revert_status and culprit.revert_status != status.COMPLETED:
      culprit.revert_status = status.ERROR
      culprit.put()

  def finalized(self):  # pragma: no cover
    self._LogUnexpectedAborting(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, repo_name, revision):
    if waterfall_config.GetActionSettings().get(
        'revert_compile_culprit', False):
      return _RevertCulprit(repo_name, revision)
    return None