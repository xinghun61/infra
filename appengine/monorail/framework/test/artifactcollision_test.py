# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for artifactcollision module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import artifactcollision
from services import service_manager
from testing import testing_helpers


class ArtifactCollisionTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = artifactcollision.ArtifactCollision(
        'rerq', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest(
        params={'name': 'artifact'}, method='POST')
    self.mr.project_name = 'monorail'
    self.mr.continue_issue_id = '123'

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('artifact', page_data['artifact_name'])
    self.assertEqual('/p/monorail/issues/detail?id=123',
                     page_data['artifact_detail_url'])
