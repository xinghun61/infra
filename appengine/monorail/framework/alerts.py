# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helpers for showing alerts at the top of the page.

These alerts are then displayed by alerts.ezt.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time

from third_party import ezt

# Expiration time for special features of timestamped links.
# This is not for security, just for informational messages that
# make sense in the context of a user session, but that should
# not appear days later if the user follows a bookmarked link.
_LINK_EXPIRATION_SEC = 8


class AlertsView(object):
  """EZT object for showing alerts at the top of the page."""

  def __init__(self, mr):
    # Used to show message confirming item was updated
    self.updated = mr.GetIntParam('updated')

    # Used to show message confirming item was moved and the location of the new
    # item.
    self.moved_to_project = mr.GetParam('moved_to_project')
    self.moved_to_id = mr.GetIntParam('moved_to_id')
    self.moved = self.moved_to_project and self.moved_to_id

    # Used to show message confirming item was copied and the location of the
    # new item.
    self.copied_from_id = mr.GetIntParam('copied_from_id')
    self.copied_to_project = mr.GetParam('copied_to_project')
    self.copied_to_id = mr.GetIntParam('copied_to_id')
    self.copied = self.copied_to_project and self.copied_to_id

    # Used to show message confirming items deleted
    self.deleted = mr.GetParam('deleted')

    # If present, we will show message confirming that data was saved
    self.saved = mr.GetParam('saved')

    link_generation_timestamp = mr.GetIntParam('ts', default_value=0)
    now = int(time.time())
    ts_links_are_valid = now - link_generation_timestamp < _LINK_EXPIRATION_SEC

    show_alert = ts_links_are_valid and (
        self.updated or self.moved or self.copied or self.deleted or self.saved)
    self.show = ezt.boolean(show_alert)
