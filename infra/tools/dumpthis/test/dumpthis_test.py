# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../dumpthis.py"""

import argparse
import unittest
import mock

from infra.tools.dumpthis import dumpthis


class DumpThisTest(unittest.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    dumpthis.add_argparse_options(parser)
    args = parser.parse_args(['--bucket', 'random'])
    self.assertEqual(args.bucket, 'random')
    args = parser.parse_args([''])
    self.assertEqual(args.src, '')
    args = parser.parse_args(['file'])
    self.assertEqual(args.src, 'file')

  @mock.patch('infra.tools.dumpthis.dumpthis.gsutil_cmd')
  def test_gsutil(self, gsutil_cmd):
    with mock.patch('infra.tools.dumpthis.dumpthis.get_destination',
                    lambda x: '%s/uuid' % x):
      dumpthis.run('BUCKET', 'FILE')
      gsutil_cmd.assert_called_with(['cp', 'FILE', 'gs://BUCKET/uuid'])
      dumpthis.run('BUCKET', '')
      gsutil_cmd.assert_called_with(['cp', '-', 'gs://BUCKET/uuid'],
                                    pipe_stdin=True)
      with mock.patch('infra.tools.dumpthis.dumpthis.get_file_type',
                      lambda x: 'text/plain; charset=us-ascii'):
        dumpthis.run('BUCKET', 'FILE')
        gsutil_cmd.assert_called_with(
            ['-h', 'Content-Type:text/plain; charset=us-ascii',
             'cp', 'FILE', 'gs://BUCKET/uuid'])
