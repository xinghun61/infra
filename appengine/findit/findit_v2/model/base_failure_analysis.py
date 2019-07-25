# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Base models for an analysis. """

from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import GitilesCommit
from libs import analysis_status


class BaseFailureAnalysis(ndb.Model):
  """A base class for a luci build."""
  # Indexed string "<luci_project>/<bucket_name>/builder_name".
  # Example: "chromium/ci/Linux Tests".
  builder_id = ndb.StringProperty(required=True)
  # The ID of the buildbucket build.
  build_id = ndb.IntegerProperty(required=True)

  # Id of the builder to run the rerun builds.
  #For chromium, it should be the findit_variables builder.
  # For chromeos, build.output.properties['BISECT_BUILDER'] is the builder.
  rerun_builder_id = ndb.StringProperty(required=True, indexed=False)

  # Regression range for the analysis to analyze.
  last_passed_commit = ndb.StructuredProperty(GitilesCommit, indexed=False)
  first_failed_commit = ndb.StructuredProperty(GitilesCommit, indexed=False)

  # Time when the analysis is created.
  create_time = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
  # Time when the analysis starts to run.
  start_time = ndb.DateTimeProperty(indexed=False)
  # Time when the analysis runs to the end.
  end_time = ndb.DateTimeProperty(indexed=False)

  # Status of the analysis, see libs.analysis_status.
  status = ndb.IntegerProperty(default=analysis_status.RUNNING, indexed=False)
  # Error code and message, if any.
  error = ndb.JsonProperty(indexed=False)

  @property
  def completed(self):
    return self.status in (analysis_status.COMPLETED, analysis_status.ERROR)

  @ndb.ComputedProperty
  def luci_project(self):
    """ID of the LUCI project to which this build belongs.
    E.g. 'chromium', 'chromeos'.
    """
    return self.builder_id.split('/', 1)[0]

  @property
  def bucket_id(self):
    """
    Format in "<luci_project>/<bucket_name>". Example: "chromium/ci".
    Includes luci_project since buckets are bounded within project, and it
    should always be searching for <luci_project>/<bucket_name> instead of
    only bucket_name.
    """
    return self.builder_id.rsplit('/', 1)[0]
