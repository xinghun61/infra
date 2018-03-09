# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra_api_clients.swarming.swarming_bot_counts import SwarmingBotCounts


class SwarmingBotCountsTest(unittest.TestCase):

  def testSerialize(self):
    counts = {
        'count': '10',
        'busy': '3',
        'dead': '1',
        'quarantined': '0',
    }
    expected_bot_counts = {
        'count': 10,
        'available': 6,
        'busy': 3,
        'dead': 1,
        'quarantined': 0,
    }

    self.assertEqual(expected_bot_counts, SwarmingBotCounts(counts).Serialize())
