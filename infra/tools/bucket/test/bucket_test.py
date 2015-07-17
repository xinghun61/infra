# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../bucket.py"""

import argparse
import unittest
import subprocess

from infra.tools.bucket import bucket


class FakeGsutil():
  def __init__(self):
    self.bucket_exists = False
    self.calls = []

  def __call__(self, args):
    print args
    self.calls.append(args)
    if len(args) == 3 and args[:2] == ['ls', '-b']:
      if not self.bucket_exists:
        raise subprocess.CalledProcessError('Failed', 1)


class MyTest(unittest.TestCase):
  def setUp(self):
    self.gsutil = FakeGsutil()
    self.old_gsutil = getattr(bucket, 'gsutil')
    setattr(bucket, 'gsutil', self.gsutil)

  def tearDown(self):
    setattr(bucket, 'gsutil', self.old_gsutil)

  def test_arguments(self):
    parser = argparse.ArgumentParser()
    bucket.add_argparse_options(parser)
    args = parser.parse_args(['bucket', 'bucket2'])
    self.assertEqual(args.bucket, ['bucket', 'bucket2'])

  def test_verify_bucket_name(self):
    self.assertTrue(bucket.bucket_is_public('chromium-public'))
    self.assertFalse(bucket.bucket_is_public('chrome-private'))
    self.assertRaises(
        bucket.InvalidBucketName, bucket.bucket_is_public, 'foobar-meow')

  def test_run_with_ccompute(self):
    bucket.run('chromium-public', True, True)
    return self.gsutil.calls

  def test_run_bucket_exists(self):
    self.gsutil.bucket_exists = True
    self.assertRaises(
        bucket.BucketExists, bucket.run, 'chromium-public', True, True)
    return self.gsutil.calls

  def test_run_without_ccompute(self):
    bucket.run('chrome-private', False, False)
    return self.gsutil.calls



