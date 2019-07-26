# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities for assisting in Flake entity operations."""

from google.appengine.ext import ndb

from model.flake.flake import Flake


@ndb.transactional
def GetFlake(luci_project, original_step_name, original_test_name, master_name,
             builder_name, build_number):
  """Returns an existing Flake or creates one as needed.

  Args:
    luci_project (str): The project being analyzed, e.g. 'chromium'.
    original_step_name (str): The original step name which may contain hardware
      information and 'with(out) patch' etc. suffixes.
    original_test_name (str): The original test name.
    master_name (str): Master name of the build of the step.
    builder_name (str): Builder name of the build of the step.
    build_number (int): Build number of the build of the step.
  """
  normalized_step_name = Flake.LegacyNormalizeStepName(
      original_step_name, master_name, builder_name, build_number)
  normalized_test_name = Flake.NormalizeTestName(original_test_name,
                                                 original_step_name)
  flake = Flake.Get(luci_project, normalized_step_name, normalized_test_name)

  if not flake:  # pragma: no branch
    label = Flake.GetTestLabelName(original_test_name, original_step_name)
    flake = Flake.Create(luci_project, normalized_step_name,
                         normalized_test_name, label)
    flake.put()

  return flake
