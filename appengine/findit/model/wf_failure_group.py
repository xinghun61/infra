# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class WfFailureGroup(BaseBuildModel):
  """Represents a group of build failures maybe caused by the same culprit CL.
  """

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key('WfFailureGroup',
                   BaseBuildModel.CreateBuildId(
                       master_name, builder_name, build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):  # pragma: no cover
    return WfFailureGroup(
        key=WfFailureGroup._CreateKey(master_name, builder_name, build_number))

  @staticmethod
  def Get(master_name, builder_name, build_number):  # pragma: no cover
    return WfFailureGroup._CreateKey(
        master_name, builder_name, build_number).get()

  # Integer representation for build failure type.
  # Refer to common/waterfall/failure_type.py for all the failure types.
  build_failure_type = ndb.IntegerProperty(indexed=True)

  # The blame list of CLs that make up the regression range for this group.
  blame_list = ndb.JsonProperty(indexed=False, compressed=True)

  # The list of compile failure output nodes (from signals).
  # Only not None if this group represents a compile failure.
  output_nodes = ndb.JsonProperty(indexed=True)

  # The failed steps and tests of a test failure (from failed_steps).
  # Only not None if this group represents a test failure.
  failed_steps_and_tests = ndb.JsonProperty(indexed=True)

  # The sorted list of suspected tuples, if available, from heuristic analysis.
  suspected_tuples = ndb.JsonProperty(indexed=False, compressed=True)
