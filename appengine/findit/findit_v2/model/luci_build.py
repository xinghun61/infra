# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Base models for a luci build.

Data models are prefixed by 'Luci' to indicate that Findit is supporting Luci
builds. And also to differentiate from the data models in v1.
"""

from google.appengine.ext import ndb

from buildbucket_proto.build_pb2 import BuilderID

from findit_v2.model.gitiles_commit import GitilesCommit
from services import git


def ParseBuilderId(builder_id):
  """Returns the builder config in a dict from a builder_id.

  Args:
    builder_id (str): Builder id in the format project/bucket/builder.

  Returns:
    build_pb2.BuilderID based on the str formatted builder_id.
  """
  parts = builder_id.split('/')

  assert len(parts) == 3, 'builder_id {} in an invalid format.'.format(
      builder_id)

  return BuilderID(
      project=parts[0],
      bucket=parts[1],
      builder=parts[2],
  )


def GetBuilderIdString(luci_project, luci_bucket, luci_builder):
  """Returns the builder_id in string representation."""
  return '{}/{}/{}'.format(luci_project, luci_bucket, luci_builder)


def SaveFailedBuild(context, build, build_failure_type):
  """Saves the failed build.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    build_failure_type (str): Type of failures in build.
  """
  repo_url = git.GetRepoUrlFromContext(context)

  build_entity = LuciFailedBuild.Create(
      luci_project=build.builder.project,
      luci_bucket=build.builder.bucket,
      luci_builder=build.builder.builder,
      build_id=build.id,
      legacy_build_number=build.number,
      gitiles_host=context.gitiles_host,
      gitiles_project=context.gitiles_project,
      gitiles_ref=context.gitiles_ref,
      gitiles_id=context.gitiles_id,
      commit_position=git.GetCommitPositionFromRevision(
          context.gitiles_id, repo_url=repo_url),
      status=build.status,
      create_time=build.create_time.ToDatetime(),
      start_time=build.start_time.ToDatetime(),
      end_time=build.end_time.ToDatetime(),
      build_failure_type=build_failure_type)
  build_entity.put()
  return build_entity


class LuciBuild(ndb.Model):
  """A base class for a luci build."""

  # The ID of the buildbucket build.
  build_id = ndb.IntegerProperty(required=True)

  # High level information to scale a build.
  # ID of the LUCI project to which this build belongs.
  # E.g. 'chromium', 'chromeos'.
  luci_project = ndb.StringProperty(required=True)
  # Indexed string "<luci_project>/<bucket_name>".
  # Example: "chromium/ci".
  # Includes luci_project since buckets are bounded within project, and it
  # should always be searching for <luci_project>/<bucket_name> instead of
  # only bucket_name.
  bucket_id = ndb.StringProperty(required=True)
  # Indexed string "<luci_project>/<bucket_name>/builder_name".
  # Example: "chromium/ci/Linux Tests".
  builder_id = ndb.StringProperty(required=True)

  # Additional information to identify a single build.
  # Integer number of the build.
  # Can identify a build using both builder_id and legacy_build_number.
  # Save legacy_build_number separately to use it traverse build history
  # more easily.
  legacy_build_number = ndb.IntegerProperty()

  # Gitles commit the build runs on.
  # Can identify a build using both builder_id and gitiles_commit in the future.
  gitiles_commit = ndb.StructuredProperty(GitilesCommit, required=True)

  # Time when the build is created.
  create_time = ndb.DateTimeProperty(indexed=False)
  # Time when the build starts to run.
  # Can be used for ordering analyses on UI or collecting metrics.
  start_time = ndb.DateTimeProperty()
  # Time when the build runs to the end.
  end_time = ndb.DateTimeProperty(indexed=False)

  # Status of the build, see common_pb2.Status.
  status = ndb.IntegerProperty()

  @classmethod
  def Create(cls,
             luci_project,
             luci_bucket,
             luci_builder,
             build_id,
             legacy_build_number,
             gitiles_host,
             gitiles_project,
             gitiles_ref,
             gitiles_id,
             commit_position,
             status,
             create_time,
             parent_key=None):
    gitiles_commit = GitilesCommit(
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=gitiles_id,
        commit_position=commit_position)

    if parent_key:  # pragma: no cover. (tested when testing CompileRerunBuild)
      # Rerun builds belong to each analysis, so they need to also set their
      # parent.
      return cls(
          luci_project=luci_project,
          bucket_id='{}/{}'.format(luci_project, luci_bucket),
          builder_id=GetBuilderIdString(luci_project, luci_bucket,
                                        luci_builder),
          build_id=build_id,
          legacy_build_number=legacy_build_number,
          gitiles_commit=gitiles_commit,
          create_time=create_time,
          status=status,
          id=build_id,
          parent=parent_key)

    return cls(
        luci_project=luci_project,
        bucket_id='{}/{}'.format(luci_project, luci_bucket),
        builder_id=GetBuilderIdString(luci_project, luci_bucket, luci_builder),
        build_id=build_id,
        legacy_build_number=legacy_build_number,
        gitiles_commit=gitiles_commit,
        create_time=create_time,
        status=status,
        id=build_id)

  @classmethod
  def GetBuildByNumber(cls, luci_project, luci_bucket, luci_builder, number):
    builds = cls.query(
        ndb.AND(
            LuciFailedBuild.builder_id == GetBuilderIdString(
                luci_project, luci_bucket, luci_builder),
            LuciFailedBuild.legacy_build_number == number)).fetch()
    return builds[0] if builds else None


class LuciFailedBuild(LuciBuild):
  """Class for a failed ci build."""
  # Whether it is a compile failure, test failure, infra failure or others.
  # Refer to findit_v2/services/failure_type.py for all the failure types.
  build_failure_type = ndb.StringProperty()

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, luci_project, luci_bucket, luci_builder, build_id,
             legacy_build_number, gitiles_host, gitiles_project, gitiles_ref,
             gitiles_id, commit_position, status, create_time, start_time,
             end_time, build_failure_type):
    instance = super(LuciFailedBuild, cls).Create(
        luci_project, luci_bucket, luci_builder, build_id, legacy_build_number,
        gitiles_host, gitiles_project, gitiles_ref, gitiles_id, commit_position,
        status, create_time)

    instance.start_time = start_time
    instance.end_time = end_time
    instance.build_failure_type = build_failure_type
    return instance
