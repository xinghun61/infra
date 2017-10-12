# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status
from libs import time_util


class RevertCL(ndb.Model):
  """Represents a reverting CL's metadata."""

  # The url of the revert CL created by Findit.
  revert_cl_url = ndb.StringProperty(indexed=False)

  # Time when the revert CL is created.
  created_time = ndb.DateTimeProperty(indexed=False)

  # Time when the revert CL is committed.
  committed_time = ndb.DateTimeProperty(indexed=False)

  # Status of this revert: COMMITTED, DUPLICATE or FALSE_POSITIVE.
  status = ndb.IntegerProperty(indexed=False)


class BaseSuspectedCL(ndb.Model):
  """Represents base information about a suspected cl."""

  # Repo or project name of the suspected CL, eg: chromium, etc.
  repo_name = ndb.StringProperty(indexed=True)

  # The Git hash revision of the suspected CL.
  revision = ndb.StringProperty(indexed=False)

  # The commit position of the suspected CL.
  # Might not be available for some repo.
  commit_position = ndb.IntegerProperty(indexed=False)

  # Time when the CL was identified as a suspect for the first time.
  identified_time = ndb.DateTimeProperty(indexed=True)

  # Time when the CL was updated.
  updated_time = ndb.DateTimeProperty(indexed=True)

  # The revert CL of this suspected CL.
  # Set only if Findit creates the reverting CL.
  revert_cl = ndb.LocalStructuredProperty(RevertCL, compressed=True)

  # A flag to indicate if revert is supposed to be done for this suspected CL.
  # It will be updated to True when Findit tries to revert it.
  should_be_reverted = ndb.BooleanProperty(indexed=True, default=False)

  # Status of the process of reverting culprit.
  revert_status = ndb.IntegerProperty(indexed=False, default=None)

  # The time the sheriff decided to take action on reverting this suspected CL.
  # If Findit's revert CL was committed, this will be the timestamp the sheriff
  # commited it. If the sheriff committed their own, this will be the timestamp
  # their revert CL was created. None if this suspected cl is a false positive.
  sheriff_action_time = ndb.DateTimeProperty(indexed=False)

  # The reason why creating revert is skipped.
  skip_revert_reason = ndb.StringProperty(indexed=False)

  # The ID of the pipeline that is reverting the culprit, if any. This value
  # should be None if the culprit is not in the process of being reverted.
  revert_pipeline_id = ndb.StringProperty(indexed=False)

  # Time when the revert is craeted.
  revert_created_time = ndb.DateTimeProperty(indexed=True)

  # Status of the process of submitting revert.
  # The statuses are described in analysis_status.py
  revert_submission_status = ndb.IntegerProperty(indexed=False, default=None)

  # The ID of the pipeline that is submitting revert of the culprit, if any.
  # This value should be None if a revert is not being submitted.
  submit_revert_pipeline_id = ndb.StringProperty(indexed=False)

  # Time when the revert is committed.
  revert_committed_time = ndb.DateTimeProperty(indexed=True)

  # When the code-review of this culprit was notified.
  cr_notification_time = ndb.DateTimeProperty(indexed=True)

  # The status of code-review notification: None, RUNNING, COMPLETED, ERROR.
  cr_notification_status = ndb.IntegerProperty(indexed=True)

  @property
  def cr_notification_processed(self):
    return self.cr_notification_status in (analysis_status.COMPLETED,
                                           analysis_status.RUNNING)

  @property
  def cr_notified(self):
    return self.cr_notification_status == analysis_status.COMPLETED

  @property
  def revert_cl_url(self):
    return self.revert_cl.revert_cl_url if self.revert_cl else None

  @property
  def project_name(self):
    return self.repo_name

  @classmethod
  def _CreateKey(cls, repo_name, revision):  # pragma: no cover
    return ndb.Key(cls.__name__, '%s/%s' % (repo_name, revision))

  @classmethod
  def Create(cls, repo_name, revision, commit_position):  # pragma: no cover
    instance = cls(key=cls._CreateKey(repo_name, revision))
    instance.repo_name = repo_name
    instance.revision = revision
    instance.commit_position = commit_position
    instance.identified_time = time_util.GetUTCNow()
    return instance

  @classmethod
  def Get(cls, repo_name, revision):  # pragma: no cover
    return cls._CreateKey(repo_name, revision).get()

  def to_dict(self):
    """Overloads ndb.Model's to_dict() method to include @property fields."""
    result_dict = super(BaseSuspectedCL, self).to_dict()
    result_dict['cr_notification_processed'] = self.cr_notification_processed
    result_dict['cr_notified'] = self.cr_notified
    result_dict['revert_cl_url'] = self.revert_cl_url
    result_dict['project_name'] = self.repo_name
    return result_dict
