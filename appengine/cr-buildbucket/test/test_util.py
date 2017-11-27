# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


def ununicide(jsonish):  # pragma: no cover
  if isinstance(jsonish, dict):
    return {ununicide(k): ununicide(v) for k, v in jsonish.iteritems()}

  if isinstance(jsonish, list):
    return map(ununicide, jsonish)

  if isinstance(jsonish, unicode):
    return str(jsonish)

  return jsonish


def future(result):  # pragma: no cover
  f = ndb.Future()
  f.set_result(result)
  return f


def future_exception(ex):  # pragma: no cover
  f = ndb.Future()
  f.set_exception(ex)
  return f
