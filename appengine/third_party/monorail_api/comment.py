# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Comment object for working with issue tracker comments."""


import re
from monorail_api.change_tracking_list import ChangeTrackingList
from monorail_api.utils import parseDateTime


class Comment(object):
  def __init__(self, comment_entry):
    self.author = comment_entry['author']['name']
    self.comment = comment_entry['content']
    self.created = parseDateTime(comment_entry['published'])
    self.id = comment_entry['id']

    updates = comment_entry.get('updates', {})
    self.owner = updates.get('owner')
    self.status = updates.get('status')
    self.merged_into = updates.get('mergedInto')
    self.cc = updates.get('cc', [])
    self.labels = updates.get('labels', [])
    self.components = updates.get('components', [])
    self.blocked_on = updates.get('blockedOn', [])
    self.blocking = updates.get('blocking', [])
