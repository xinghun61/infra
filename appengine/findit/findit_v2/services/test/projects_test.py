# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from parameterized import parameterized
import unittest

from findit_v2.services import projects
from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.failure_type import BuilderTypeEnum


class ProjectsTest(unittest.TestCase):

  def testGetProjectAPI(self):
    self.assertTrue(
        isinstance(projects.GetProjectAPI('chromeos'), ChromeOSProjectAPI))

  @parameterized.expand([
      ('chromium', 'ci', 'Linux Builder', BuilderTypeEnum.SUPPORTED),
      ('chromium', 'ci', 'Linux Tests', BuilderTypeEnum.UNSUPPORTED),
      ('chromeos', 'postsubmit', 'xx-postsubmit', BuilderTypeEnum.SUPPORTED),
      ('chromeos', 'postsubmit', 'postsubmit-orchestrator',
       BuilderTypeEnum.SUPPORTED),
      ('chromeos', 'bisect', 'xx-bisect', BuilderTypeEnum.RERUN),
      ('chromeos', 'bisect', 'bisecting-orchestrator', BuilderTypeEnum.RERUN),
      ('chromeos', 'postsubmit', 'bisecting-orchestrator',
       BuilderTypeEnum.UNSUPPORTED),
  ])
  def testGetBuilderType(self, project, bucket, builder, builder_type):
    self.assertEqual(builder_type,
                     projects.GetBuilderType(project, bucket, builder))
