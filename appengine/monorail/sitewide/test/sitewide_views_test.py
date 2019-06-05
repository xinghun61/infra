# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for sitewide_views module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import usergroup_pb2
from sitewide import sitewide_views


class GroupViewTest(unittest.TestCase):

  def testConstructor(self):
    group_settings = usergroup_pb2.MakeSettings('anyone')
    view = sitewide_views.GroupView('groupname', 123, group_settings, 999)

    self.assertEqual('groupname', view.name)
    self.assertEqual(123, view.num_members)
    self.assertEqual('ANYONE', view.who_can_view_members)
    self.assertEqual('/g/999/', view.detail_url)
