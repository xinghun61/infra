# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class TreeStatus(ndb.Model):
  """Represents a tree status."""

  time = ndb.DateTimeProperty(indexed=False)
  message = ndb.StringProperty(indexed=False)
  # The state of the tree: open, close, throttle.
  state = ndb.StringProperty(indexed=False)
  username = ndb.StringProperty(indexed=False)

  @ndb.ComputedProperty
  def closed(self):
    return self.state.lower() != 'open'

  @ndb.ComputedProperty
  def automatic(self):
    return self.username == 'buildbot@chromium.org'


class TreeClosure(ndb.Model):
  """Represents a tree closure."""

  tree_name = ndb.StringProperty(indexed=True)
  statuses = ndb.StructuredProperty(TreeStatus, repeated=True, indexed=False)

  closed_time = ndb.DateTimeProperty(indexed=True)
  opened_time = ndb.DateTimeProperty(indexed=False)
  # The time of the last status remained open before next closure.
  latest_action_time = ndb.DateTimeProperty(indexed=False)

  auto_closed = ndb.BooleanProperty(indexed=True)
  auto_opened = ndb.BooleanProperty(indexed=True)

  possible_flake = ndb.BooleanProperty(indexed=True)
  has_revert = ndb.BooleanProperty(indexed=True)

  master_name = ndb.StringProperty(indexed=True)
  builder_name = ndb.StringProperty(indexed=True)
  build_id = ndb.StringProperty(indexed=False)
  # Which step triggers this closure like 'compile'.
  step_name = ndb.StringProperty(indexed=True)
