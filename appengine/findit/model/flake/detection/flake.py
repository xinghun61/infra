# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_issue import FlakeIssue

class Flake(ndb.Model):
  """Parent Flake which FlakeOccurrences are grouped under."""

  # Used in conjunction with test_name to identify the test.
  step_name = ndb.StringProperty(indexed=True)

  # Used in conjunction with step_name to identify the test.
  test_name = ndb.StringProperty(indexed=True)

  # Flake occurrence instances.
  flake_occurrences = ndb.StructuredProperty(FlakeOccurrence, repeated=True)

  # Issue object that's attached.
  flake_issue = ndb.StructuredProperty(FlakeIssue)

  # Project id in monorail (e.g. chromium).
  project_id = ndb.StringProperty(indexed=True)
