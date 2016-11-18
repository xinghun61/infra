# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs delta test on 2 findit versions."""

import argparse
from datetime import date
from datetime import timedelta
import logging
import os
import pickle
import sys

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                           os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)

import script_util
script_util.SetUpSystemPaths()

from crash_queries.delta_test import delta_test
from crash_queries.delta_test import delta_util

_TODAY = date.today().strftime('%Y-%m-%d')
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')

# App Engine APIs will fail if batch size is more than 1000.
_MAX_BATCH_SIZE = 1000
_DEFAULT_BATCH_SIZE = _MAX_BATCH_SIZE

DELTA_RESULTS_DIRECTORY = os.path.join(os.path.dirname(__file__),
                                       'delta_results')
CHROMIUM_REPO = 'https://chromium.googlesource.com/chromium/src'


def RunDeltaTest():
  """Runs delta testing between two different Predator versions."""
  argparser = argparse.ArgumentParser(
      description='Run delta test between two Predator revisions. Note, since '
      'the delta test needs to switch on different revisions of predator repo, '
      'please commit any local change before running delta test, and do not '
      ' make any new changes while running the delta test.')

  argparser.add_argument(
      '--revisions',
      '-r',
      nargs='+',
      default=['HEAD^', 'HEAD'],
      help=('The Predator revisions to be compared. It can take '
            'one or two revisions seperated by empty spaces.\n'
            '(1) -r rev1 rev2: compare rev1 and rev2\n'
            '(2) -r rev: compare rev and current HEAD\n'
            '(3) no revisions provided, default to compare HEAD^ and HEAD'))

  argparser.add_argument(
      '--client',
      '-c',
      default='fracas',
      help=('Possible values are: fracas, cracas, clusterfuzz. Right now, only '
            'fracas is supported.'))

  argparser.add_argument(
      '--app',
      '-a',
      default=os.getenv('APP_ID', 'findit-for-me-dev'),
      help=('App id of the App engine app that query needs to access. '
            'Defualts to findit-for-me-dev. You can set enviroment variable by'
            ' \'export APP_ID=your-app-id\' to replace the default value.'))

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
      '--batch',
      '-b',
      type=int,
      default=_DEFAULT_BATCH_SIZE,
      help=('The size of batch that can be processed at one time.\n'
            'Note, the batch size cannot be greater than 1000, or app engine '
            'APIs would fail.\nDefaults to maximum number 1000.'))

  argparser.add_argument(
      '--verbose',
      '-v',
      action='store_true',
      default=False,
      help='Print findit results. Defaults to False.')

  args = argparser.parse_args()

  # If in verbose mode, prints debug information.
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)

  if len(args.revisions) > 2:
    logging.error('Only support delta test between 2 versions.')
    sys.exit(1)

  if args.batch > _MAX_BATCH_SIZE:
    logging.error('Batch size cannot be greater than %s, or app engine APIs '
                  'would fail.', _MAX_BATCH_SIZE)
    sys.exit(1)

  # If only one revision provided, default the rev2 to HEAD.
  if len(args.revisions) == 1:
    args.revisions.append('HEAD')

  git_hash1 = delta_util.ParseGitHash(args.revisions[0])
  git_hash2 = delta_util.ParseGitHash(args.revisions[1])

  delta_result_prefix = '%s_%s_%s..%s.delta' % (git_hash1[:7], git_hash2[:7],
                                                args.since, args.until)
  delta_csv_path = os.path.join(DELTA_RESULTS_DIRECTORY,
                                '%s.csv' % delta_result_prefix)
  delta_path = os.path.join(DELTA_RESULTS_DIRECTORY,
                            delta_result_prefix)

  # Check if delta results already existed.
  if os.path.exists(delta_csv_path):
    print 'Delta results existed in\n%s' % delta_csv_path
    if not os.path.exists(delta_path):
      print 'Cannot print out delta results, please open %s to see the results.'
      return

    with open(delta_path) as f:
      deltas, crash_num = pickle.load(f)
  else:
    print 'Running delta test...'
    print ('WARNING: Please commit any local change before running delta test, '
           'and do not make any new changes while running the delta test.')
    # Get delta of results between git_hash1 and git_hash2.
    deltas, crash_num = delta_test.DeltaEvaluator(
        git_hash1, git_hash2, args.client, args.app,
        start_date=args.since, end_date=args.until,
        batch_size=args.batch, verbose=args.verbose)
    delta_util.FlushResult([deltas, crash_num], delta_path)
    delta_util.WriteDeltaToCSV(deltas, crash_num, args.app,
                               git_hash1, git_hash2, delta_csv_path)

  # Print delta results to users.
  print '\n========================= Summary ========================='
  delta_util.PrintDelta(deltas, crash_num, args.app)


if __name__ == '__main__':
  RunDeltaTest()
