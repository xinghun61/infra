# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


def future(result):  # pragma: no coverage
  f = ndb.Future()
  f.set_result(result)
  return f
