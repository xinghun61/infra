# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.loglinear.changelist_features.number_of_touched_files import (
    NumberOfTouchedFilesFeature)
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from libs.gitiles.change_log import FileChangeInfo


class NumberOfTouchedFilesFeatureTest(PredatorTestCase):
  """Tests ``NumberOfTouchedFilesFeature`` feature."""

  def setUp(self):
    super(NumberOfTouchedFilesFeatureTest, self).setUp()
    self._feature = NumberOfTouchedFilesFeature()

  def testCall(self):
    """Tests ``__call__`` method."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')

    touched_file = FileChangeInfo.FromDict({'old_path': None,
                                            'new_path': 'a.cc',
                                            'change_type': 'add'})
    suspect.changelog = suspect.changelog._replace(
        touched_files=[touched_file]*15)
    self.assertEqual(self._feature(None)(suspect).value, 0.0)
