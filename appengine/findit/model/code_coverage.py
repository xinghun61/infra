# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb


class DependencyRepository(ndb.Model):
  # The source absolute path of the checkout into the root repository.
  # Example: "//third_party/pdfium/" for pdfium in a chromium/src checkout.
  path = ndb.StringProperty(indexed=False, required=True)

  # The Gitiles hostname, e.g. "pdfium.googlesource.com".
  server_host = ndb.StringProperty(indexed=False, required=True)

  # The Gitiles project name, e.g. "pdfium.git".
  project = ndb.StringProperty(indexed=False, required=True)

  # The commit hash of the revision.
  revision = ndb.StringProperty(indexed=False, required=True)

  @property
  def project_url(self):
    return 'https://%s/%s' % (self.server_host, self.project)


class GitilesCommit(ndb.Model):
  """Represents a Gitiles commit."""

  # The Gitiles hostname, e.g. "chromium.googlesource.com".
  server_host = ndb.StringProperty(indexed=True, required=True)

  # The Gitiles project name, e.g. "chromium/src".
  project = ndb.StringProperty(indexed=True, required=True)

  # The giiles ref, e.g. "refs/heads/master".
  # NOT a branch name: if specified, must start with "refs/".
  ref = ndb.StringProperty(indexed=True, required=True)

  # The commit hash of the revision.
  revision = ndb.StringProperty(indexed=False, required=True)


class PostsubmitReport(ndb.Model):
  """Represents a postsubmit code coverage report."""

  # The Gitiles commit.
  gitiles_commit = ndb.StructuredProperty(
      GitilesCommit, indexed=True, required=True)

  # An optional increasing numeric number assigned to each commit.
  commit_position = ndb.IntegerProperty(indexed=True, required=False)

  # Timestamp when the commit was committed.
  commit_timestamp = ndb.DateTimeProperty(indexed=True, required=True)

  # TODO(crbug.com/939443): Make it required once data are backfilled.
  # Name of the luci builder that generates the data.
  bucket = ndb.StringProperty(indexed=True, required=False)
  builder = ndb.StringProperty(indexed=True, required=False)

  # Manifest of all the code checkouts when the coverage report is generated.
  # In descending order by the length of the relative path in the root checkout.
  manifest = ndb.LocalStructuredProperty(
      DependencyRepository, repeated=True, indexed=False)

  # The top level coverage metric of the report.
  # For Clang based languages, the format is a list of 3 dictionaries
  # corresponds to 'line', 'function' and 'region' respectively, and each dict
  # has format: {'covered': 9526650, 'total': 12699841, 'name': u'|name|'}
  summary_metrics = ndb.JsonProperty(indexed=False, required=True)

  # The build id that uniquely identifies the build.
  build_id = ndb.IntegerProperty(indexed=False, required=True)

  # Used to control if a report is visible to the users, and the main use case
  # is to quanrantine a 'bad' report. All the reports are visible to admins.
  visible = ndb.BooleanProperty(indexed=True, default=False, required=True)

  @classmethod
  def _CreateKey(cls, server_host, project, ref, revision, bucket, builder):
    return ndb.Key(
        cls, '%s$%s$%s$%s$%s$%s' % (server_host, project, ref, revision, bucket,
                                    builder))

  @classmethod
  def Create(cls,
             server_host,
             project,
             ref,
             revision,
             bucket,
             builder,
             commit_timestamp,
             manifest,
             summary_metrics,
             build_id,
             visible,
             commit_position=None):
    key = cls._CreateKey(server_host, project, ref, revision, bucket, builder)
    gitiles_commit = GitilesCommit(
        server_host=server_host, project=project, ref=ref, revision=revision)
    return cls(
        key=key,
        gitiles_commit=gitiles_commit,
        bucket=bucket,
        builder=builder,
        commit_position=commit_position,
        commit_timestamp=commit_timestamp,
        manifest=manifest,
        summary_metrics=summary_metrics,
        build_id=build_id,
        visible=visible)

  @classmethod
  def Get(cls, server_host, project, ref, revision, bucket, builder):
    entity = cls._CreateKey(server_host, project, ref, revision, bucket,
                            builder).get()
    if entity:
      return entity

    # TODO(crbug.com/939443): Remove following code once data are backfilled.
    legacy_key = ndb.Key(cls,
                         '%s$%s$%s$%s' % (server_host, project, ref, revision))
    return legacy_key.get()


class CLPatchset(ndb.Model):
  """Represents a CL patchset."""

  # The Gerrit hostname, e.g. "chromium-review.googlesource.com".
  server_host = ndb.StringProperty(indexed=True, required=True)

  # The Gerrit project name, e.g. "chromium/src".
  # Note that project is optional because the other three already uniquely
  # identifies a CL patchset.
  project = ndb.StringProperty(indexed=True, required=False)

  # The Gerrrit change number, e.g. "138000".
  change = ndb.IntegerProperty(indexed=True, required=True)

  # The Gerrit patchset number, e.g. "2".
  patchset = ndb.IntegerProperty(indexed=True, required=True)


def PercentageValidator(_, value):
  """Validates that the total number of lines is greater than 0."""
  if value <= 0:
    raise datastore_errors.BadValueError(
        'total_lines is expected to be greater than 0.')

  return value


class CoveragePercentage(ndb.Model):
  """Represents code coverage percentage metric for a file.

  It is stored as a part of PresubmitCoverageData.
  """

  # The source absolute path of the file. E.g. //base/test.cc.
  path = ndb.StringProperty(indexed=False, required=True)

  # Total number of lines.
  total_lines = ndb.IntegerProperty(
      indexed=False, required=True, validator=PercentageValidator)

  # Number of covered lines.
  covered_lines = ndb.IntegerProperty(indexed=False, required=True)


class PresubmitCoverageData(ndb.Model):
  """Represents the code coverage data of a change during presubmit."""

  # The CL patchset.
  cl_patchset = ndb.StructuredProperty(CLPatchset, indexed=True, required=True)

  # The build id that uniquely identifies the build.
  build_id = ndb.IntegerProperty(indexed=False, required=True)

  # A list of file level coverage data for all the source files modified by the
  # this CL.
  data = ndb.JsonProperty(indexed=False, compressed=True, required=True)

  # Coverage percentages of all executable lines of the files.
  absolute_percentages = ndb.LocalStructuredProperty(
      CoveragePercentage, indexed=False, repeated=True)

  # Coverage percentages of *newly added* and executable lines of the files.
  incremental_percentages = ndb.LocalStructuredProperty(
      CoveragePercentage, indexed=False, repeated=True)

  @classmethod
  def _CreateKey(cls, server_host, change, patchset):
    return ndb.Key(cls, '%s$%s$%s' % (server_host, change, patchset))

  @classmethod
  def Create(cls, server_host, change, patchset, build_id, data, project=None):
    key = cls._CreateKey(server_host, change, patchset)
    cl_patchset = CLPatchset(
        server_host=server_host,
        project=project,
        change=change,
        patchset=patchset)
    return cls(key=key, cl_patchset=cl_patchset, build_id=build_id, data=data)

  @classmethod
  def Get(cls, server_host, change, patchset):
    return cls._CreateKey(server_host, change, patchset).get()


class FileCoverageData(ndb.Model):
  """Represents the code coverage data of a single file.

  File can be from a dependency checkout, and it can be a generated file instead
  of a source file checked into the repo.
  """

  # The Gitiles commit.
  gitiles_commit = ndb.StructuredProperty(
      GitilesCommit, indexed=True, required=True)

  # Source absoluate file path.
  path = ndb.StringProperty(indexed=True, required=True)

  # TODO(crbug.com/939443): Make it required once data are backfilled.
  # Name of the luci builder that generates the data.
  bucket = ndb.StringProperty(indexed=True, required=False)
  builder = ndb.StringProperty(indexed=True, required=False)

  # Coverage data for a single file.
  data = ndb.JsonProperty(indexed=False, compressed=True, required=True)

  @classmethod
  def _CreateKey(cls, server_host, project, ref, revision, path, bucket,
                 builder):
    return ndb.Key(
        cls, '%s$%s$%s$%s$%s$%s$%s' % (server_host, project, ref, revision,
                                       path, bucket, builder))

  @classmethod
  def Create(cls, server_host, project, ref, revision, path, bucket, builder,
             data):
    assert path.startswith('//'), 'File path must start with "//"'

    key = cls._CreateKey(server_host, project, ref, revision, path, bucket,
                         builder)
    gitiles_commit = GitilesCommit(
        server_host=server_host, project=project, ref=ref, revision=revision)
    return cls(
        key=key,
        gitiles_commit=gitiles_commit,
        path=path,
        bucket=bucket,
        builder=builder,
        data=data)

  @classmethod
  def Get(cls, server_host, project, ref, revision, path, bucket, builder):
    entity = cls._CreateKey(server_host, project, ref, revision, path, bucket,
                            builder).get()
    if entity:
      return entity

    # TODO(crbug.com/939443): Remove following code once data are backfilled.
    legacy_key = ndb.Key(
        cls, '%s$%s$%s$%s$%s' % (server_host, project, ref, revision, path))
    return legacy_key.get()


class SummaryCoverageData(ndb.Model):
  """Represents the code coverage data of a directory or a component."""

  # The Gitiles commit.
  gitiles_commit = ndb.StructuredProperty(
      GitilesCommit, indexed=True, required=True)

  # Type of the summary coverage data.
  data_type = ndb.StringProperty(
      indexed=True, choices=['dirs', 'components'], required=True)

  # Source absoluate path to the file or path to the components. E.g:
  # // or /media/cast/net/rtp/frame_buffer.cc for directories.
  # >> or Blink>Fonts for components.
  path = ndb.StringProperty(indexed=True, required=True)

  # TODO(crbug.com/939443): Make them required once data are backfilled.
  # Name of the luci builder that generates the data.
  bucket = ndb.StringProperty(indexed=True, required=False)
  builder = ndb.StringProperty(indexed=True, required=False)

  # Coverage data for a directory or a component.
  data = ndb.JsonProperty(indexed=False, compressed=True, required=True)

  @classmethod
  def _CreateKey(cls, server_host, project, ref, revision, data_type, path,
                 bucket, builder):
    return ndb.Key(
        cls, '%s$%s$%s$%s$%s$%s$%s$%s' % (server_host, project, ref, revision,
                                          data_type, path, bucket, builder))

  @classmethod
  def Create(cls, server_host, project, ref, revision, data_type, path, bucket,
             builder, data):
    if data_type == 'dirs':
      assert path.startswith('//'), 'Directory path must start with //'

    key = cls._CreateKey(server_host, project, ref, revision, data_type, path,
                         bucket, builder)
    gitiles_commit = GitilesCommit(
        server_host=server_host, project=project, ref=ref, revision=revision)
    return cls(
        key=key,
        gitiles_commit=gitiles_commit,
        data_type=data_type,
        path=path,
        bucket=bucket,
        builder=builder,
        data=data)

  @classmethod
  def Get(cls, server_host, project, ref, revision, data_type, path, bucket,
          builder):
    entity = cls._CreateKey(server_host, project, ref, revision, data_type,
                            path, bucket, builder).get()
    if entity:
      return entity

    # TODO(crbug.com/939443): Remove following code once data are backfilled.
    legacy_key = ndb.Key(
        cls, '%s$%s$%s$%s$%s$%s' % (server_host, project, ref, revision,
                                    data_type, path))
    return legacy_key.get()
