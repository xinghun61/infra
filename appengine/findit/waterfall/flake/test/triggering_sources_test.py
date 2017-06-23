# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from waterfall.flake import triggering_sources


class FlakeAnalysisServiceTest(unittest.TestCase):

  def testGetDescriptionForTriggeringSource(self):
    self.assertEqual('The analysis was triggered manually through Findit UI',
                     triggering_sources.GetDescriptionForTriggeringSource(
                         triggering_sources.FINDIT_UI, True))
    self.assertEqual('The analysis was triggered manually through Findit API',
                     triggering_sources.GetDescriptionForTriggeringSource(
                         triggering_sources.FINDIT_API, True))
    self.assertEqual(
        'The analysis was triggered automatically through Findit pipeline',
        triggering_sources.GetDescriptionForTriggeringSource(
            triggering_sources.FINDIT_PIPELINE, False))
    self.assertEqual(
        'The analysis was triggered automatically through Findit API',
        triggering_sources.GetDescriptionForTriggeringSource(
            triggering_sources.FINDIT_API, False))
