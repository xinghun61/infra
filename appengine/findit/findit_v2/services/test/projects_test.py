# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services import projects


class ProjectsTest(unittest.TestCase):

  def testGetProjectAPI(self):
    self.assertTrue(
        isinstance(projects.GetProjectAPI('chromeos'), ChromeOSProjectAPI))
