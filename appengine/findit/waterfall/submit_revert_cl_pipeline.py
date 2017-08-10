# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from libs import time_util
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import create_revert_cl_pipeline
from waterfall import suspected_cl_util
from waterfall import waterfall_config

_DEFAULT_AUTO_COMMIT_DAILY_THRESHOLD = 4
_DEFAULT_CULPRIT_COMMIT_LIMIT_HOURS = 24


@ndb.transactional
def _CanCommitRevert(repo_name, revision, pipeline_id):
  """Checks if current pipeline should do the auto commit.

  This pipeline should commit a revert of the culprit if:
    1. There is a revert for the culprit;
    2. The revert have copleted;
    3. The revert should be auto commited;
    4. No other pipeline is committing the revert;
    5. No other pipeline is supposed to handle the auto commit.
  """
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  if (not culprit.revert_cl or
      culprit.revert_submission_status == status.COMPLETED or
      culprit.revert_status != status.COMPLETED or
      culprit.revert_submission_status == status.SKIPPED or
      (culprit.revert_submission_status == status.RUNNING and
       culprit.submit_revert_pipeline_id and
       culprit.submit_revert_pipeline_id != pipeline_id)):
    return False

  # Update culprit to ensure only current analysis can commit the revert.
  culprit.revert_submission_status = status.RUNNING
  culprit.submit_revert_pipeline_id = pipeline_id
  culprit.put()
  return True


@ndb.transactional
def _UpdateCulprit(repo_name, revision, revert_submission_status=None):
  culprit = WfSuspectedCL.Get(repo_name, revision)

  culprit.revert_submission_status = (revert_submission_status or
                                      culprit.revert_submission_status)

  if culprit.revert_submission_status != status.RUNNING:
    culprit.submit_revert_pipeline_id = None

  if culprit.revert_submission_status == status.COMPLETED:
    culprit.revert_committed_time = time_util.GetUTCNow()

  culprit.put()
  return culprit


def _GetDailyNumberOfCommits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO (chanli): improve the check for a rare case when two pipelines commit
  # at the same time.
  return WfSuspectedCL.query(
      WfSuspectedCL.revert_committed_time >= earliest_time).count(limit)


def _ShouldCommitRevert(repo_name, revision, revert_status, pipeline_id):
  """Checks if the revert should be auto committed.


  The revert should be committed if:
    1. Auto revert and Auto commit is turned on;
    2. The revert is created by Findit;
    3. This pipeline can commit the revert;
    4. The number of commits of reverts in past 24 hours is less than the
      daily limit;
    5. The revert is done in Gerrit;
    6. The culprit is committed within threshold.
  """
  action_settings = waterfall_config.GetActionSettings()
  if (not revert_status == create_revert_cl_pipeline.CREATED_BY_FINDIT or
      not bool(action_settings.get('commit_gerrit_revert')) or
      not bool(action_settings.get('revert_compile_culprit'))):
    return False

  if not _CanCommitRevert(repo_name, revision, pipeline_id):
    return False

  auto_commit_daily_threshold = action_settings.get(
      'auto_commit_daily_threshold', _DEFAULT_AUTO_COMMIT_DAILY_THRESHOLD)
  if _GetDailyNumberOfCommits(
      auto_commit_daily_threshold) >= auto_commit_daily_threshold:
    logging.info('Auto commits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  culprit_commit_limit_hours = action_settings.get(
      'culprit_commit_limit_hours', _DEFAULT_CULPRIT_COMMIT_LIMIT_HOURS)

  # Gets Culprit information.
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)
  culprit_change_id = culprit_info['review_change_id']
  culprit_host = culprit_info['review_server_host']

  # Makes sure codereview is Gerrit, as only Gerrit is supported at the moment.
  if not codereview_util.IsCodeReviewGerrit(culprit_host):
    _UpdateCulprit(repo_name, revision, status.SKIPPED)
    return False

  # Makes sure the culprit landed less than x hours ago (default: 24 hours).
  # Bail otherwise.
  codereview = codereview_util.GetCodeReviewForReview(culprit_host)
  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  culprit_commit = culprit_cl_info.GetCommitInfoByRevision(revision)
  culprit_commit_time = culprit_commit.timestamp

  if time_util.GetUTCNow() - culprit_commit_time > timedelta(
      hours=culprit_commit_limit_hours):
    logging.info('Culprit %s/%s was committed over %d hours ago, stop auto '
                 'commit.' % (repo_name, revision, culprit_commit_limit_hours))
    _UpdateCulprit(repo_name, revision, status.SKIPPED)
    return False

  return True


class SubmitRevertCLPipeline(BasePipeline):

  def __init__(self, repo_name, revision, _):
    super(SubmitRevertCLPipeline, self).__init__(repo_name, revision, _)
    self.repo_name = repo_name
    self.revision = revision

  def _LogUnexpectedAborting(self, was_aborted):
    if not was_aborted:  # pragma: no cover
      return

    culprit = WfSuspectedCL.Get(self.repo_name, self.revision)

    if culprit.submit_revert_pipeline_id == self.pipeline_id:
      if (culprit.revert_submission_status and
          culprit.revert_submission_status != status.COMPLETED):
        culprit.revert_submission_status = status.ERROR
      culprit.submit_revert_pipeline_id = None
      culprit.put()

  def finalized(self):  # pragma: no cover
    self._LogUnexpectedAborting(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, repo_name, revision, revert_status):
    if not _ShouldCommitRevert(repo_name, revision, revert_status,
                               self.pipeline_id):
      return False

    culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)
    culprit_host = culprit_info['review_server_host']
    codereview = codereview_util.GetCodeReviewForReview(culprit_host)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    revert_cl = culprit.revert_cl
    revert_cl_url = revert_cl.revert_cl_url
    revert_change_id = codereview.GetChangeIdFromReviewUrl(revert_cl_url)

    committed = codereview.SubmitRevert(revert_change_id)

    if committed:
      _UpdateCulprit(repo_name, revision, status.COMPLETED)
    else:
      _UpdateCulprit(repo_name, revision, status.ERROR)
    return committed
