# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains datastore models used by this app."""

from google.appengine.ext import ndb


class Alert(ndb.Model):
  """Datastore model of the alerts sent out by this app.

  Properties:
    sender: The sender we haven't received a heartbeat email from in awhile.
    timestamp: The most recent time the app alerted the watchlist.
    total: The total number of alert emails that have been sent.
  """
  # Only index on sender because the only input to this app is a sender email.
  sender = ndb.StringProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True, indexed=False)
  total = ndb.IntegerProperty(indexed=False)


class MostRecentAlert(Alert):
  """Datastore model of a most recent alert."""
  pass


class Config(ndb.Model):
  """Datastore model of a configuration.

  Properties:
    sender: The sender email address.
    timeout: The maximum number of minutes between heartbeats before notifying
      the watchlist.
    watchlist: A set of email addresses to notify if an email hasn't been
      received in a number of minutes exceeding the given timeout.
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
  timestamp = ndb.DateTimeProperty(auto_now_add=True, indexed=False)


class MostRecentHeartbeat(Heartbeat):
  """Datastore model of a most recent heartbeat."""
  pass
