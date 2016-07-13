# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Dumpthis."""

from infra.path_hacks.depot_tools import _depot_tools as depot_tools_path
import logging
import os
import subprocess
import sys
import uuid
import base64


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


def get_file_type(path):  # pragma: no cover
  if not os.path.exists(path):
    return None

  try:
    out = subprocess.check_output(['file', '--mime-type', '-L', path])
    return out.strip().split(":")[-1].strip()
  except (ValueError, IndexError, subprocess.CalledProcessError):
    return None

def gsutil_cmd(args, pipe_stdin=False):  # pragma: no cover
  target = os.path.join(depot_tools_path, 'gsutil.py')
  cmd = [sys.executable, target, '--force-version', '4.11', '--'] + args
  if pipe_stdin:
    subprocess.check_call(cmd, stdin=sys.stdin, stderr=subprocess.PIPE)
  else:
    subprocess.check_call(cmd)


def get_destination(bucket):  # pragma: no cover
  # uuid4 is to avoid collission, but 48 bits of randomness is enough.
  # base32 => to condense 48 bits into 10 chars long name with no dashes.
  name = base64.b32encode(uuid.uuid4().bytes[:6]).rstrip('=').lower()
  return '%s/%s' % (bucket, name)


def run(bucket, src, media_type=None):
  LOGGER.info('Dumpthis starting.')

  header = []
  if src and not media_type:
    media_type = get_file_type(src)
  if media_type:
    header = ['-h', 'Content-Type:%s' % media_type]

  destination = get_destination(bucket)
  gs_dest = 'gs://%s' % destination

  if src:
    gsutil_cmd(header + ['cp', src, gs_dest])
  else:
    gsutil_cmd(header + ['cp', '-', gs_dest], pipe_stdin=True)

  print
  print 'Use https://storage.cloud.google.com/%s' % destination


def argparse_mime_type(s):
  s = s.strip()
  short = {
    'txt': 'text/plain',
    'html': 'text/html',
    'png': 'image/png',
  }
  return short.get(s) or s


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument(
      'src', nargs='?', help='file you want to upload, else uses stdin')
  parser.add_argument(
      '-b', '--bucket', default='chrome-dumpfiles',
      help='a Google Storage bucket to dump to')
  parser.add_argument(
      '-t', '--media-type', default=None, type=argparse_mime_type,
      help='Media type. Useful if you want browser to display it, instead of '
           'downloading. Short values of (txt, html, png) supported, otherwise '
           'use full media type like text/plain or image/png. '
           'See list at '
           'http://www.iana.org/assignments/media-types/media-types.xhtml')
