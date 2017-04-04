# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from datetime import date
from datetime import timedelta
import os
import sys

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                           os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)
import script_util
script_util.SetUpSystemPaths()

from crash_queries.crash_printer import crash_printer

_DATETIME_FORMAT = '%Y-%m-%d'
_TODAY = date.today().strftime(_DATETIME_FORMAT)
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime(_DATETIME_FORMAT)


if __name__ == '__main__':
  argparser = argparse.ArgumentParser(
      description='Print crashes.')

  argparser.add_argument(
      '--since',
      '-s',
      default=_A_YEAR_AGO,
      help=('Query data since this date (including this date). '
            'Should be in YYYY-MM-DD format. E.g. 2015-09-31. '
            'Defaults to a year ago.'))

  argparser.add_argument(
      '--until',
      '-u',
      default=_TODAY,
      help=('Query data until this date (not including this date). '
            'Should be in YYYY-MM-DD format. E.g. 2015-09-31. '
            'Defaults to today.'))

  argparser.add_argument(
      '--client',
      '-c',
      default='cracas',
      help=('Possible values are: fracas, cracas, clusterfuzz. Right now, only '
            'fracas is supported.'))

  argparser.add_argument(
      '--app',
      '-a',
      default=os.getenv('APP_ID', 'predator-for-me-staging'),
      help=('App id of the App engine app that query needs to access. '
            'Defualts to findit-for-me-dev. You can set enviroment variable by'
            ' \'export APP_ID=your-app-id\' to replace the default value.'))

  argparser.add_argument(
      '--signature',
      help='Signature of the crash.')

  args = argparser.parse_args()

  crash_printer.CrashPrinter(args.client, args.app,
                             start_date=args.since, end_date=args.until,
                             signature=args.signature)
