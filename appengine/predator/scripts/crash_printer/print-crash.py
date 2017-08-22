# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

_ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__),
                             os.path.pardir, os.path.pardir))
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)
from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from scripts.crash_printer import crash_printer
from scripts import setup


if __name__ == '__main__':
  argparser = argparse.ArgumentParser(
      description='Print crashes.')

  argparser.add_argument(
      '--since',
      '-s',
      default=setup.A_YEAR_AGO,
      help=('Query data since this date (including this date). '
            'Should be in YYYY-MM-DD format. E.g. 2015-09-31. '
            'Defaults to a year ago.'))

  argparser.add_argument(
      '--until',
      '-u',
      default=setup.TODAY,
      help=('Query data until this date (not including this date). '
            'Should be in YYYY-MM-DD format. E.g. 2015-09-31. '
            'Defaults to today.'))

  argparser.add_argument(
      '--client',
      '-c',
      default=setup.DEFAULT_CLIENT,
      help=('Possible values are: fracas, cracas, clusterfuzz. Right now, only '
            'fracas is supported. Defaults to \'%s\'.') % setup.DEFAULT_CLIENT)

  argparser.add_argument(
      '--app',
      '-a',
      default=setup.DEFAULT_APP_ID,
      help=('App id of the App engine app that query needs to access. '
            'Defaults to \'%s\'.') % setup.DEFAULT_APP_ID)

  argparser.add_argument(
      '--signature',
      help='Signature of the crash.')

  args = argparser.parse_args()

  crash_printer.CrashPrinter(args.client, args.app,
                             start_date=args.since, end_date=args.until,
                             signature=args.signature)
