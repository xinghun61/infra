# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


def get_branch(svn_log_entry, full=False):
  for path in svn_log_entry.paths:
    m = re.search("/branches/(?:chromium/)?(.*?)/", path.filename,
                  re.IGNORECASE)
    if m:
      if full:
        return m.group(0)
      else:
        return m.group(1)
  return None