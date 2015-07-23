# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Wrapper tool for creating a new bucket in Chrome Infra.

Example invocation:
./run.py infra.tools.bucket <bucket name>

Bucket name should start with "chromium-" or "chrome-".
chromium-* buckets are publicly readable by default
chrome-* are google readable by default
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import sys

from infra.tools.bucket import bucket
import infra_libs.logs


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="bucket",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  bucket.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  LOGGER.info('Bucket starting.')

  for bucket_name in args.bucket:
    public = bucket.bucket_is_public(bucket_name)
    bucket.run(bucket_name, args.ccompute, public)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
