# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.detection.flake_issue import FlakeIssue


class Flake(ndb.Model):
  """Parent Flake which FlakeOccurrences are grouped under."""

  # Used in conjunction with test_name to identify the test.
  step_name = ndb.StringProperty(indexed=True)

  # Used in conjunction with step_name to identify the test.
  test_name = ndb.StringProperty(indexed=True)

  # Issue object that's attached.
  flake_issue = ndb.StructuredProperty(FlakeIssue)

  # Project id in monorail (e.g. chromium).
  project_id = ndb.StringProperty(indexed=True)

  @staticmethod
  def GetId(step_name, test_name):
    assert step_name
    assert test_name
    return '{}/{}'.format(step_name, test_name)

  @staticmethod
  def Get(step_name, test_name):
    """Get a flake for step/test if it exists."""
    flake_key = ndb.Key(Flake, Flake.GetId(step_name, test_name))
    return flake_key.get()

  @staticmethod
  def Create(step_name, test_name, flake_issue=None, project_id=None):
    """Create a flake for step/test and any other kwargs."""
    flake_id = Flake.GetId(step_name, test_name)
    return Flake(
        step_name=step_name,
        test_name=test_name,
        flake_issue=flake_issue,
        project_id=project_id,
        id=flake_id)
