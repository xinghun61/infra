# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../cache_updater.py"""

import argparse
import unittest

from infra.services.cache_updater import cache_updater


class CacheUpdaterTests(unittest.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    cache_updater.add_argparse_options(parser)
    args = cache_updater.parse_args(
        parser, ['--shard-total', '10', '--shard-index', '5'])
    self.assertEqual(args.shard_total, 10)
    self.assertEqual(args.shard_index, 5)

    self.assertRaises(
        SystemExit, cache_updater.parse_args, parser,
        ['--shard-total', '5', '--shard-index', '10'])
    self.assertRaises(
        SystemExit, cache_updater.parse_args, parser,
        ['--shard-total', '-5', '--shard-index', '10'])
    self.assertRaises(
        SystemExit, cache_updater.parse_args, parser,
        ['--shard-total', '5', '--shard-index', '-10'])

  def test_shard(self):
    test_in = ['https://someurl.com', 'a', 'b', 'c']
    return [cache_updater.shard(url, 5) for url in test_in]
