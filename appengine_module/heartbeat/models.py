# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains datastore models used by this app."""

from google.appengine.ext import ndb


class Config(ndb.Model):
  """Datastore model of a configuration.

  Properties:
    sender: The sender email address.
    timeout: The maximum number of seconds between heartbeats before notifying
      the watchlist.
    watchlist: A set of email addresses to notify if an email hasn't been
      received in a number of seconds exceeding the given timeout.
  """
  # Only index on sender because the only input to this app is a sender email.
  sender = ndb.StringProperty()
  timeout = ndb.IntegerProperty(indexed=False)
  watchlist = ndb.StringProperty(indexed=False, repeated=True)


class Heartbeat(ndb.Model):
  """Datastore model of a heartbeat.

  Properties:
    sender: The sender email address.
    timestamp: The timestamp of the most recently received heartbeat from this
      sender.
  """
  # Only index on sender because the only input to this app is a sender email.
  sender = ndb.StringProperty()
  timestamp = ndb.TimeProperty(indexed=False)


class MostRecentHeartbeat(Heartbeat):
  """Datastore model of a most recent heartbeat."""
  pass
