# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import webapp2

from google.appengine.ext import ndb

from model.flake import Issue
from common import data_interface, monorail_interface


DAYS_TO_REOPEN_ISSUE = 3


@ndb.transactional(xg=True) # pylint: disable=no-value-for-parameter
def _delete_old_and_insert_new(old_issue, new_issue):
  old_issue.key.delete()
  return new_issue.put()


def _recreate_issue(issue):
  flake_types = [
      flake_type_key.get()
      for flake_type_key in issue.flake_type_keys
  ]

  new_issue_id = monorail_interface.recreate_issue(
      issue.project, issue.issue_id, flake_types)
  new_issue = Issue(project=issue.project, issue_id=new_issue_id,
                    flake_type_keys=issue.flake_type_keys)

  return _delete_old_and_insert_new(issue, new_issue)


def _update_issue_with_id(issue, new_project, new_issue_id):
  # If there is another entity for the new_issue_id, we update it's flake types.
  # Otherwise, we "update" the issue id by deleting the entity and creating
  # another one with the same info and another id.
  # TODO(ehmaldonado): Consider updating issue_id field in the existing entity.
  issues = Issue.query(Issue.project == new_project,
                       Issue.issue_id == new_issue_id).fetch(1)

  if not issues:
    new_issue = Issue(project=new_project, issue_id=new_issue_id,
                      flake_type_keys=issue.flake_type_keys)
    new_issue.put()
  else:
    new_issue = issues[0]
    new_issue.flake_type_keys = list(set(
        issue.flake_type_keys + new_issue.flake_type_keys))

  flake_types = [
      flake_type_key.get()
      for flake_type_key in new_issue.flake_type_keys
  ]
  monorail_interface.post_notice(new_project, new_issue_id, flake_types)

  return _delete_old_and_insert_new(issue, new_issue)


def update_issue_ids(flakes_by_issue):
  new_flakes_by_issue = {}
  for issue_key, flakes in flakes_by_issue.items():
    issue = issue_key.get()

    monorail_issue = monorail_interface.follow_duplication_chain(
        issue.project, issue.issue_id)

    if monorail_issue is None:
      # If an issue duplication loop was detected, we re-create the issue.
      issue_key = _recreate_issue(issue)

    elif not monorail_issue.open:
      # If the issue was closed, we do not update it. This allows changes made
      # to reduce flakiness to propagate and take effect. If we still detect
      # flakiness after DAYS_TO_REOPEN_ISSUE days, we will create a new issue.
      now = datetime.datetime.utcnow()
      recent_cutoff = now - datetime.timedelta(days=DAYS_TO_REOPEN_ISSUE)
      if monorail_issue.closed >= recent_cutoff:
        continue
      issue_key = _recreate_issue(issue)

    elif (issue.issue_id != monorail_issue.id
        or issue.project != monorail_issue.project_id):
      # If after following the duplication chain, we arrive at a new issue we
      # should notify the users that this issue will now be used by Chromium Try
      # Flakes to post information about new flaky failures.
      issue_key = _update_issue_with_id(issue, monorail_issue.project_id,
                                        monorail_issue.id)

    new_flakes_by_issue.setdefault(issue_key, []).extend(flakes)

  return new_flakes_by_issue
