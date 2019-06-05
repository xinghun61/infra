# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View objects to help display users and groups in UI templates."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging


class GroupView(object):
  """Class to make it easier to display user group metadata."""

  def __init__(self, name, num_members, group_settings, group_id):
    self.name = name
    self.num_members = num_members
    self.who_can_view_members = str(group_settings.who_can_view_members)
    self.group_id = group_id

    self.detail_url = '/g/%s/' % group_id
