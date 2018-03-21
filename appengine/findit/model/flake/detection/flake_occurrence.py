# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from protorpc import messages

from model.flake.detection.flake import Flake


class FlakeType(messages.Enum):
  """Enumerates the different types of flakes."""

  # A developer is falsely rejected from CQ by a flake.
  # Described fully here: http://shortn/_P1wlxtDO7d.
  CQ_FALSE_REJECTION = 100

  # A test flakes by first failing multiple times before passing.
  # Described fully here: http://shortn/_P1wlxtDO7d.
  OUTRIGHT_FLAKE = 200


class FlakeOccurrence(ndb.Model):
  """Tracks a specific Flake Occurrence on a particular configuration."""

  # Used to identify the configuration.
  master_name = ndb.StringProperty(indexed=True)

  # Used to identify the configuration.
  builder_name = ndb.StringProperty(indexed=True)

  # Used to identify the specific build.
  build_number = ndb.IntegerProperty(indexed=True)

  # Used to identify the specific build.
  build_id = ndb.IntegerProperty(indexed=True)

  # The time the flake occurrence was reported.
  time_reported = ndb.DateTimeProperty(indexed=True)

  # The type of the flake.
  flake_type = msgprop.EnumProperty(FlakeType)

  @staticmethod
  def Get(step_name, test_name, build_id):
    """Get a flake for step/test if it exists."""
    flake_key = ndb.Key(Flake, Flake.GetId(step_name, test_name))
    flake_occurrences = FlakeOccurrence.query(
        FlakeOccurrence.build_id == build_id, ancestor=flake_key).fetch()
    return flake_occurrences[0] if flake_occurrences else None

  @staticmethod
  def Create(step_name, test_name, build_id, master_name, builder_name,
             build_number, time_reported, flake_type):
    """Create a flake for step/test and any other kwargs."""
    assert build_id
    assert master_name
    assert builder_name
    assert build_number
    assert time_reported
    assert flake_type

    flake_key = ndb.Key(Flake, Flake.GetId(step_name, test_name))
    assert flake_key.get()

    return FlakeOccurrence(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=time_reported,
        flake_type=flake_type,
        parent=flake_key)
