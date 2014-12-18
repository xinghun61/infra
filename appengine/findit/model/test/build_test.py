# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import unittest

from model.build import Build
from model.build_analysis_status import BuildAnalysisStatus


class BuildTest(unittest.TestCase):
  def testReset(self):
    build = Build()
    build.analysis_status = BuildAnalysisStatus.ERROR
    build.analysis_start_time = datetime.utcnow()
    build.analysis_updated_time = datetime.utcnow()

    build.Reset()

    self.assertEqual(BuildAnalysisStatus.PENDING, build.analysis_status)
    self.assertIsNone(build.analysis_start_time)
    self.assertIsNone(build.analysis_updated_time)
