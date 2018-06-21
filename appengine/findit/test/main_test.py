# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

import backend_main
import frontend_main


class MainTest(testing.AppengineTestCase):

  def testImportInMainIsAllGood(self):
    # Should not raise any exception if handler importing is all good.

    # We have to import this module here, because endpoints_webapp2.api_server
    # requires app_id being set in environment variables which is mocked by
    # testing.AppengineTestCase.
    import default_main  # pylint: disable=unused-variable
