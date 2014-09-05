# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file defines datastore models used throughout the app."""

__author__ = 'agable@google.com (Aaron Gable)'


from google.appengine.ext import ndb


class EmailList(ndb.Model):
  """Represents a list of email addresses.

  Does not perform any validation on the email addresses.

  This app uses the id/name (unique datastore key) of the object to hold the
  google-group email address to which all these emails belong.

  Attributes:
    emails: List of strings, one per email.
  """
  emails = ndb.StringProperty(repeated=True)
