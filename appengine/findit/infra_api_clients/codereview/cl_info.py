# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An abstraction of a ChangeList's relevant information."""

from libs import time_util


class Commit(object):  # pragma: no cover

  def __init__(self, patchset_id, revision, timestamp):
    # A string such as '20001'.
    self.patchset_id = patchset_id
    # A commit hash e.g. 'abcd0123abcd0123abcd0123abcd0123abcd0123'.
    self.revision = revision
    # The timestamp of the message as stored in the code review issue.
    self.timestamp = timestamp

  def serialize(self):
    return {
        'patchset_id': self.patchset_id,
        'revision': self.revision,
        'timestamp': time_util.FormatDatetime(self.timestamp),
    }


class Revert(object):  # pragma: no cover

  def __init__(self, patchset_id, reverting_cl, reverting_user_email,
               timestamp):
    # A string such as '20001'
    self.patchset_id = patchset_id
    # A ClInfo object
    self.reverting_cl = reverting_cl
    # The user who created the revert (the sender of the message).
    self.reverting_user_email = reverting_user_email
    # The message's timestamp.
    self.timestamp = timestamp

  def serialize(self):
    result = {
        'patchset_id': self.patchset_id,
        'reverting_user_email': self.reverting_user_email,
        # Time of reverting patch creation.
        'timestamp': time_util.FormatDatetime(self.timestamp),
    }
    if self.reverting_cl:
        result['reverting_cl'] = self.reverting_cl.serialize()
    return result


class ClInfo(object):  # pragma: no cover

  def __init__(self, review_url):
    self.url = review_url
    # A list of Commit objects.
    self.commits = []
    # A list of Revert objects.
    self.reverts = []
    # Boolean, None for undetermined.
    self.closed = None
    # List of emails to cc
    self.cc = []
    # List of reviewers' emails
    self.reviewers = []

  def serialize(self):
    return {
        'url': self.url,
        'commits': [x.serialize() for x in self.commits],
        'reverts': [x.serialize() for x in self.reverts],
        'closed': self.closed,
        'cc': self.cc,
        'reviewers': self.reviewers,
    }

  def GetPatchsetIdByRevision(self, revision):
    for commit in self.commits:
      if commit.revision == revision:  # pragma: no branch
        return commit.patchset_id
    return None  # pragma: no cover

  def GetRevertCLsByRevision(self, revision):
    patchset_id = self.GetPatchsetIdByRevision(revision)
    if not patchset_id:  # pragma: no cover
      return None

    reverts_for_revision = []
    for revert in self.reverts:
      if revert.patchset_id == patchset_id:  # pragma: no branch
        reverts_for_revision.append(revert)
    return reverts_for_revision