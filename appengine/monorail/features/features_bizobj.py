# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Business objects for the Monorail features.

These are classes and functions that operate on the objects that users care
about in features (eg. hotlists).
"""

import logging

from framework import framework_bizobj
from framework import urls
from proto import features_pb2

def GetOwnerIds(hotlist):
  return hotlist.owner_ids

def UsersInvolvedInHotlists(hotlists):
  result = set()
  for hotlist in hotlists:
    result.update(hotlist.owner_ids)
    result.update(hotlist.editor_ids)
    result.update(hotlist.follower_ids)
  return result
