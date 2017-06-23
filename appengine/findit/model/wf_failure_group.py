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
                   BaseBuildModel.CreateBuildId(master_name, builder_name,
                                                build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):  # pragma: no cover
    return WfFailureGroup(key=WfFailureGroup._CreateKey(
        master_name, builder_name, build_number))

  @staticmethod
  def Get(master_name, builder_name, build_number):  # pragma: no cover
    return WfFailureGroup._CreateKey(master_name, builder_name,
                                     build_number).get()

  # Integer representation for build failure type.
  # Refer to common/waterfall/failure_type.py for all the failure types.
  build_failure_type = ndb.IntegerProperty(indexed=True)

  # When the group was created.
  created_time = ndb.DateTimeProperty(indexed=True)

  # The blame list of CLs that make up the regression range for this group.
  blame_list = ndb.JsonProperty(indexed=False, compressed=True)

  # The list of compile failure output nodes (from signals).
  # Only not None if this group represents a compile failure.
  output_nodes = ndb.JsonProperty(indexed=False)

  # A sorted list of lists of the failed steps and tests of a test failure.
  # Only not None if this group represents a test failure.
  # Example:
  # [
  #     ['step_a', 'test1'],
  #     ['step_a', 'test2'],
  #     ['step_b', None]
  # ]
  # ndb.JsonProperty uses json.dumps() without sort_keys=True, which causes
  # dicts that are identical except for their internal key order to have
  # different JSON representations. So, for the failed_steps_and_tests JSON
  # property, a list is used instead of a dict (json.dumps() preserves the order
  # of list elements). This enables a WfFailureGroup query based on equivalent
  # failed_steps_and_tests to return all of the matching results, instead of
  # missing some results. Missing results is a possibility if
  # failed_steps_and_tests used a dict, and the keys of the original dict (that
  # went to the database) were JSONified to string in a different order than the
  # keys of the dict used in the query. For example:
  # '{"step_a": [], "step_y": []}' versus '{"step_y": [], "step_a": []}'.
  failed_steps_and_tests = ndb.JsonProperty(indexed=False)

  # The sorted list of suspected tuples, if available, from heuristic analysis.
  suspected_tuples = ndb.JsonProperty(indexed=False, compressed=True)
