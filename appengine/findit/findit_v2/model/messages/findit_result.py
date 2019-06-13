# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from protorpc import messages

# This is used by the underlying ProtoRpc when creating names for the ProtoRPC
# messages below. This package name will show up as a prefix to the message
# class names in the discovery doc and client libraries.
package = 'FindIt'


# Alternative way to identify a build by using
# luci_project/bucket/builder/build_number.
class BuildIdentifierByNumber(messages.Message):
  # Luci project ID, e.g. "chromium". Unique within a LUCI deployment.
  project = messages.StringField(1)

  # Bucket name, e.g. "try". Unique within the project.
  bucket = messages.StringField(2)

  # Builder name, e.g. "linux-rel". Unique within the bucket.
  builder = messages.StringField(3)

  # Build number.
  number = messages.IntegerField(4, variant=messages.Variant.INT32)


# Represents a failed build with its failed steps.
class BuildFailureAnalysisRequest(messages.Message):
  # Build id.
  # Can be used alone to identify a build.
  build_id = messages.IntegerField(1, variant=messages.Variant.INT64)

  # Alternative id to identify a build. Will be ignored if build_id is also
  # provided.
  build_alternative_id = messages.MessageField(BuildIdentifierByNumber, 2)

  # Failed steps in the build reported by the client.
  # Optional. When provided Findit will only respond analysis results of the
  # requested steps, otherwise respond analysis of the whole build.
  failed_steps = messages.StringField(3, repeated=True)


class BuildFailureAnalysisRequestCollection(messages.Message):
  requests = messages.MessageField(
      BuildFailureAnalysisRequest, 1, repeated=True)


# A Gerrit patchset with some extra information related to Findit actions.
# pylint: disable=line-too-long
# Reference: https://chromium.googlesource.com/infra/luci/luci-go/+/a3f01e2ec089d7bad5552f400c1b7255c2758911/buildbucket/proto/common.proto#130
class GerritChange(messages.Message):
  # Gerrit hostname, e.g. "chromium-review.googlesource.com".
  host = messages.StringField(1)
  # Gerrit project, e.g. "chromium/src".
  project = messages.StringField(2)
  # Change number, e.g. 12345.
  change = messages.IntegerField(3, variant=messages.Variant.INT64)
  # Patch set number, e.g. 1.
  patchset = messages.IntegerField(4, variant=messages.Variant.INT64)
  # Flag indicates if the change has landed or not.
  is_landed = messages.BooleanField(5, variant=messages.Variant.BOOL)


# A landed Git commit hosted on Gitiles.
# pylint: disable=line-too-long
# Reference: https://chromium.googlesource.com/infra/luci/luci-go/+/a3f01e2ec089d7bad5552f400c1b7255c2758911/buildbucket/proto/common.proto#142
class GitilesCommit(messages.Message):
  # Gitiles hostname, e.g. "chromium.googlesource.com".
  host = messages.StringField(1)

  # Repository name on the host, e.g. "chromium/src".
  project = messages.StringField(2)

  # Commit HEX SHA1.
  id = messages.StringField(3)

  # Commit ref, e.g. "refs/heads/master".
  # NOT a branch name: if specified, must start with "refs/".
  ref = messages.StringField(4)

  # Defines a total order of commits on the ref.
  commit_position = messages.IntegerField(5, variant=messages.Variant.INT32)


# A gitiles commit which is responsible for failures in a build.
# This commit can be found by Findit's heuristic analysis or rerun-based
# analysis or both.
# If Findit reverts it automatically, the revert's information will also
# be included.
class Culprit(messages.Message):
  # Information about the commit.
  commit = messages.MessageField(GitilesCommit, 1)

  # Information about the auto-created revert by Findit for this commit.
  revert = messages.MessageField(GerritChange, 2)

  # Message to display as-is on SoM or other systems in markdown format.
  # Could be used to show how Findit finds the culprit or what auto action has
  # been taken.
  culprit_markdown = messages.StringField(3)


# Analysis result of one failure:
# if Findit gets information at test level, the result will be for a single
# failed test
# Otherwise the result will be for a failed step.
class BuildFailureAnalysisResponse(messages.Message):
  # Information to identify a failure.
  # Identifier of the failed build. Will be the same as the request.
  # Build id.
  # Can be used alone to identify a build.
  build_id = messages.IntegerField(1, variant=messages.Variant.INT64)

  # Alternative id to identify a build.
  build_alternative_id = messages.MessageField(BuildIdentifierByNumber, 2)

  # Name of the step that contains failures.
  # This should be the same step name on the build with all the prefixes and
  # suffixes.
  # For example:
  # + browser_tests
  # + content_browsertests
  # + content_browsertests on Windows-10-15063
  step_name = messages.StringField(3)

  # Name of the fail test. This field will be empty if there's no test level
  # information or it's a compile failure.
  test_name = messages.StringField(4)

  # Findit's findings for the specific failure.
  # Updated regression range.
  # The latest commit that the failure passed.
  last_passed_commit = messages.MessageField(GitilesCommit, 5)
  # The earliest commit that the failure occurred.
  first_failed_commit = messages.MessageField(GitilesCommit, 6)

  # Commits found by Findit that caused the failure.
  culprits = messages.MessageField(Culprit, 7, repeated=True)

  # Is the analysis on this failure finished.
  is_finished = messages.BooleanField(8, variant=messages.Variant.BOOL)

  # Is the failure supported by Findit.
  is_supported = messages.BooleanField(9, variant=messages.Variant.BOOL)

  # Does a test fail due to flakiness.
  # This field is irrelevant to compile failures.
  is_flaky_test = messages.BooleanField(10, variant=messages.Variant.BOOL)

  # Message to display as-is on SoM or other systems in markdown format.
  # For analysis level message, like 'Findit analyzing, see [details](link)'
  # or 'Not supported by Findit', etc.
  analysis_markdown = messages.StringField(11)


class BuildFailureAnalysisResponseCollection(messages.Message):
  responses = messages.MessageField(
      BuildFailureAnalysisResponse, 1, repeated=True)
