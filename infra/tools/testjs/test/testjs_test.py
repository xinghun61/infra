# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../testjs.py"""

import argparse
import unittest
import random
import mock
import contextlib
import os

from infra.tools.testjs import testjs
from infra_libs import utils


class TestJsTest(unittest.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    testjs.add_argparse_options(parser)
    args = parser.parse_args(['chrome'])
    self.assertEqual(args.target, ['chrome'])

  @mock.patch('subprocess.Popen')
  @mock.patch('os.path.exists')
  @mock.patch('random.choice')
  def test_get_display(self, choice, exists, popen):
    choice.return_value = 102
    exists.side_effect = [False, True]
    fake_popen = mock.MagicMock()
    fake_popen.poll.return_value = None
    fake_popen.pid = 1234
    popen.return_value = fake_popen
    with utils.temporary_directory() as tempdir:
      tempfile = os.path.join(tempdir, 'pidfile')
      real_tempfile = '%s102' % tempfile
      with open(real_tempfile, 'w') as f:
        f.write('1234')
      testjs.LOCK_LOCATION = '%s%%d' % tempfile
      with testjs.get_display() as display:
        self.assertEquals(display, ':102')

  @mock.patch('subprocess.call')
  def test_karma(self, _call):
    with mock.patch.dict(os.environ, {'foo': 'bar'}):
      testjs.test_karma('somedir', 'stable', ':99')

