# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

class Password(ndb.Model):
  sha1 = ndb.StringProperty(required=True)
