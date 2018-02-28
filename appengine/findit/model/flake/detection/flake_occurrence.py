# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from protorpc import messages

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
