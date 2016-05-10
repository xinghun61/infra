# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../__main__.py"""

import argparse
import unittest
import mock

from infra.tools.log import log
from infra.tools.log import __main__ as log_main


class MainTests(unittest.TestCase):
  def test_main_options(self):
    parser = argparse.ArgumentParser()
    l = log_main.Log()
    l.add_argparse_options(parser)
    args = parser.parse_args(['cat', 'bootstrap'])
    self.assertEquals(args.command, 'cat')
    self.assertEquals(args.target, ['bootstrap'])

  @mock.patch('infra.tools.log.log.LogQuery', autospec=True)
  def test_main(self, _lq):
    args = mock.MagicMock()
    args.command = 'list'
    log_main.Log().main(args)
    # The class is used.
    self.assertGreaterEqual(len(_lq.mock_calls), 1)
