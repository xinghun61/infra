# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from services import build_url
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeReportUtilTest(WaterfallTestCase):

  def testCreateBuildUrl(self):
    master_name = 'master_name'
    builder_name = 'builder_name'
    build_number = 321

    build_link = build_url.CreateBuildUrl(master_name, builder_name,
                                          build_number)
    self.assertIn(master_name, build_link)
    self.assertIn(builder_name, build_link)
    self.assertIn(str(build_number), build_link)
