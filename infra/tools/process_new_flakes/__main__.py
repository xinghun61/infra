# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""process-new-flakes creates/updates issue for flaky tests."""

import argparse
import logging
import sys

import infra_libs.logs


def main(argv):
  parser = argparse.ArgumentParser(prog="process-new-flakes",
                                   description=sys.modules['__main__'].__doc__)
  parser.add_argument('--crbug-service-account', required=True,
                      help='Path to a service account JSON file to be used to '
                           'create/update issues on crbug.com.')
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)
  logging.debug('Crbug service account: %s', args.crbug_service_account)

  # TODO(sergiyb): Actually implement the script.
  logging.info('process-new-flakes script is not implemented yet')
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
