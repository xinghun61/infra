# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Bucket."""

import logging
import os
import sys
import subprocess

from infra.path_hacks.depot_tools import _depot_tools as depot_tools_path

# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)

PROJECT = '824709284458'
CCOMPUTE_USER = '182615506979@project.gserviceaccount.com'


class BucketExists(Exception):
  pass
class InvalidBucketName(Exception):
  pass


def gsutil(args):  # pragma: no cover
  target = os.path.join(depot_tools_path, 'gsutil.py')
  cmd = [sys.executable, target, '--']
  cmd.extend(args)
  print 'gsutil',
  print ' '.join(args)
  return subprocess.check_call(cmd, stderr=subprocess.PIPE)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--no-ccompute', '-n',
                      dest='ccompute', action='store_false',
                      help='Don\'t give GCE bots write access.')
  parser.add_argument('bucket', type=str, nargs='+')


def ensure_no_bucket_exists(bucket):
  """Raises an exception if the bucket exists."""
  try:
    gsutil(['ls', '-b', 'gs://%s' % bucket])
  except subprocess.CalledProcessError:
    return
  raise BucketExists('%s already exists.' % bucket)


def bucket_is_public(bucket_name):
  """Verify the name of the bucket and return whether it's public or not."""
  if bucket_name.startswith('chromium-'):
    return True
  elif bucket_name.startswith('chrome-'):
    return False
  else:
    raise InvalidBucketName(
        '%s does not start with either "chromium-" or "chrome-"' % bucket_name)


def run(bucket_name, ccompute, public):
  ensure_no_bucket_exists(bucket_name)
  gsutil(['mb', '-p', PROJECT, 'gs://%s' % bucket_name])
  if ccompute:
    gsutil(['acl', 'ch', '-u', '%s:w' % CCOMPUTE_USER, 'gs://%s' % bucket_name])

  if public:
    reader = 'AllUsers'
  else:
    reader = 'google.com'
  gsutil(['acl', 'ch', '-g', '%s:R' % reader, 'gs://%s' % bucket_name])
  gsutil(['defacl', 'ch', '-g', '%s:R' % reader, 'gs://%s' % bucket_name])



