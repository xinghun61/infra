# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import db


class TestLocation(db.Model):  # pylint: disable=W0232
  # Entity's key is the name of the test.
  file = db.StringProperty()
  line = db.IntegerProperty()
