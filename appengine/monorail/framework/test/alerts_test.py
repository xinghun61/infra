# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for alert display helpers."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest

from third_party import ezt

from framework import alerts
from testing import fake
from testing import testing_helpers


class AlertsViewTest(unittest.TestCase):

  def testTimestamp(self):
    """Tests that alerts are only shown when the timestamp is valid."""
    project = fake.Project(project_name='testproj')

    now = int(time.time())
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/testproj/?updated=10&ts=%s' % now, project=project)
    alerts_view = alerts.AlertsView(mr)
    self.assertEqual(10, alerts_view.updated)
    self.assertEqual(ezt.boolean(True), alerts_view.show)

    now -= 10
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/testproj/?updated=10&ts=%s' % now, project=project)
    alerts_view = alerts.AlertsView(mr)
    self.assertEqual(ezt.boolean(False), alerts_view.show)

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/testproj/?updated=10', project=project)
    alerts_view = alerts.AlertsView(mr)
    self.assertEqual(ezt.boolean(False), alerts_view.show)
