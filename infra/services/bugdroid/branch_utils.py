# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import urllib2


def get_mstone(branch, raise_exception=True):
  # TODO(crbug.com/1002078): Remove this hard-coded hack once chromiumdash adds
  # an endpoint to provide the same branch/milestone information. That interface
  # is TBD, but should be something like:
  #
  #   milestones_json = urllib2.urlopen(
  #     'https://chromiumdash.appspot.com/branches/mstone?limit=5')
  #   recent_milestones = json.load(milestones_json)
  #
  # Note, the result should probably also be memoized, since it should almost
  # always be constant throughout a given run of bugdroid (and in the rare case
  # where bugdroid runs at exactly the time when a new milestone branch is being
  # created, there's not likely to be any legitimate bugs for that brand new
  # branch), so no need to repeatedly fetch the data.
  recent_milestones = {
      '3729': 74,
      '3770': 75,
      '3809': 76,
      '3865': 77,
      '3904': 78,
  }
  if not recent_milestones and raise_exception:
    raise Exception('Failed to fetch milestone data')
  return recent_milestones.get(str(branch), None)
