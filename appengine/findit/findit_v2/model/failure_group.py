# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import GitilesCommit


class BaseFailureGroup(ndb.Model):
  """A base class for a failure group.

  Each group uses the Id of the first build in group as its id. And it stores
  information from the first build and use them to compare failures from other
  builds and decide if those failures can be grouped or not.
  """

  # ID of the LUCI project to which this build belongs.
  # E.g. 'chromium', 'chromeos'.
  luci_project = ndb.StringProperty(required=True)

  # Indexed string "<luci_project>/<bucket_name>".
  # Example: "chromium/ci".
  # Includes luci_project since buckets are bounded within project, and it
  # should always be searching for <luci_project>/<bucket_name> instead of
  # only bucket_name.
  bucket_id = ndb.StringProperty(required=True)

  # Regression range of the failures in the first build.
  last_passed_commit = ndb.StructuredProperty(GitilesCommit, indexed=False)
  first_failed_commit = ndb.StructuredProperty(GitilesCommit)

  # Time when the group is created.
  create_time = ndb.DateTimeProperty(required=True, auto_now_add=True)

  @classmethod
  def Create(cls, luci_project, luci_bucket, build_id, gitiles_host,
             gitiles_project, gitiles_ref, last_passed_gitiles_id,
             last_passed_commit_position, first_failed_gitiles_id,
             first_failed_commit_position):  # pragma: no cover.
    """Creates an entity for a failure group.

    Args:
      build_id (str): Id of the first build when creating the group.
    """
    last_passed_commit = GitilesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=last_passed_gitiles_id,
        commit_position=last_passed_commit_position)

    first_failed_commit = GitilesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=first_failed_gitiles_id,
        commit_position=first_failed_commit_position)

    return cls(
        luci_project=luci_project,
        bucket_id='{}/{}'.format(luci_project, luci_bucket),
        last_passed_commit=last_passed_commit,
        first_failed_commit=first_failed_commit,
        id=build_id)
