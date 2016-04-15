# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import urllib2


def get_mstone(branch, raise_exception=True):
  try:
    u = urllib2.urlopen('https://chromepmo.appspot.com/history/'
                        'mstone?branch=%s' % str(branch))
  except Exception:
    return None
  data = json.load(u)
  u.close()

  if data and "error" in data and raise_exception:
    raise Exception(data["error"])

  if data and "mstone" in data:
    return int(data["mstone"])

  return None