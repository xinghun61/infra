# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gerrit client for GAE environment."""

from collections import namedtuple

# pylint: disable=W0611
from gitiles.googlesource import (GoogleSourceServiceClient, Error,
                                  AuthenticationError)


Owner = namedtuple('Owner', ['name', 'email', 'username'])


Revision = namedtuple('Revision', [
    # Commit sha, such as d283186300411e4d05ef0ced6c29fe77e8767a43.
    'commit',
    # Ordinal of the revision within a GerritChange, starting from 1.
    'number',
    # A ref where this commit can be fetched.
    'fetch_ref',
])


Change = namedtuple('Change', [
    # A "long" change id, such as
    # chromium/src~master~If1bfd2e7d0ad2c14908e5d45a513b5335d36ff01
    'id',
    # A "short" change id, such as If1bfd2e7d0ad2c14908e5d45a513b5335d36ff01
    'change_id',
    'project',
    'branch',
    'subject',
    # Owner of the Change, of type Owner.
    'owner',
    # Sha of the current revision's commit.
    'current_revision',
    # A list of Revision objects.
    'revisions',
])


class GerritClient(GoogleSourceServiceClient):
  """Client class for Gerrit operations."""

  def get_change(self, change_id, include_all_revisions=True,
                 include_owner_details=False):
    """Gets a single Gerrit change by id.

    Returns Change object, or None if change was not found.
    """
    path = 'changes/%s' % change_id
    if include_owner_details:
      path += '/detail'
    if include_all_revisions:
      path += '?o=ALL_REVISIONS'
    data = self._fetch(path)
    if data is None:
      return None

    owner = None
    ownerData = data.get('owner')
    if ownerData:  # pragma: no branch
      owner = Owner(
          name=ownerData.get('name'),
          email=ownerData.get('email'),
          username=ownerData.get('username'),
      )

    revisions = [Revision(
        commit=key,
        number=int(value['_number']),
        fetch_ref=value['fetch']['http']['ref'],
    ) for key, value in data.get('revisions', {}).iteritems()]
    revisions.sort(key=lambda r: r.number)

    return Change(
        id=data['id'],
        project=data.get('project'),
        branch=data.get('branch'),
        subject=data.get('subject'),
        change_id=data.get('change_id'),
        current_revision=data.get('current_revision'),
        revisions=revisions,
        owner=owner,
    )

  def set_review(self, change_id, revision, message=None, labels=None,
                 notify=True):  # pragma: no cover
    """Sets review on a revision.

    Args:
      change_id: Gerrit change id, such as project~branch~I1234567890.
      revision: a commit sha for the patchset to review.
      message: text message.
      labels: a dict of label names and their values, such as {'Verified': 1}.
      notify: who to notify. Supported values:
        None - use default behavior, same as 'ALL'.
        'NONE': do not notify anyone.
        'OWNER': notify owner of the change_id.
        'OWNER_REVIEWERS': notify owner and OWNER_REVIEWERS.
        'ALL': notify anyone interested in the Change.
    """
    if notify is not None:
      notify = str(notify).upper()
    assert notify in (None, 'NONE', 'OWNER', 'OWNER_REVIEWERS', 'ALL')
    body = {
        'message': message,
        'labels': labels,
        'notify': notify,
    }
    body = {k:v for k, v in body.iteritems() if v is not None}

    path = 'changes/%s/revisions/%s/review' % (change_id, revision)
    self._fetch(path, 'POST', body=body)
