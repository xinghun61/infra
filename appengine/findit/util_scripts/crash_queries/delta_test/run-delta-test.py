# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs delta test on two Predator revisions."""

import argparse
from datetime import date
from datetime import timedelta
import logging
import os
import pickle
import sys

_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           os.path.pardir, os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)
import script_util
script_util.SetUpSystemPaths()

from crash.type_enums import CrashClient
from crash_queries.delta_test import delta_test
from crash_queries.delta_test import delta_util

_TODAY = date.today().strftime('%Y-%m-%d')
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')

# App Engine APIs will fail if batch size is more than 1000.
_MAX_BATCH_SIZE = 1000
_DEFAULT_BATCH_SIZE = _MAX_BATCH_SIZE
_DEFAULT_MAX_N = 100

DELTA_RESULTS_DIRECTORY = os.path.join(os.path.dirname(__file__),
                                       'delta_results')


def GenerateDeltaCSVPath(directory, git_hash1, git_hash2,
                         since_date, until_date, max_n):
  """Returns the file path of delta result."""
  delta_result_prefix = '%s_%s_%s..%s_max_%d.delta.csv' % (
      git_hash1[:7], git_hash2[:7], since_date, until_date, max_n)

  return os.path.join(directory, delta_result_prefix)


def RunDeltaTest():
  """Runs delta testing between two different Predator revisions."""
  argparser = argparse.ArgumentParser(
      description=('Delta test is a script to report the differences between '
                   'analysis results of two local repo revisions. Local git '
                   'checkouts are used instead of Gitile to avoid quota '
                   'issue.\nNOTE, since the delta test needs to switch on '
                   'different revisions of local repo, please commit all local '
                   'changes before running the script, and do not make any '
                   'new changes while running it.'))

  argparser.add_argument(
      '--revisions',
      '-r',
      nargs='+',
      default=['HEAD^', 'HEAD'],
      help=('The Predator revisions to be compared. It can take '
            'one or two revisions seperated by empty spaces. N.B. The revision '
            'can be any format that git can recognize, for example, it can be '
            'either "97312dbc1" or "HEAD~5"\n'
            '(1) -r rev1 rev2: compare rev1 and rev2\n'
            '(2) -r rev: compare rev and current HEAD\n'
            '(3) no revisions provided, default to compare HEAD^ and HEAD'))

  argparser.add_argument(
      '--client',
      '-c',
      default=CrashClient.CRACAS,
      help=('Type of client data the delta test is running on, '
            'possible values are: fracas, cracas, clusterfuzz. '
            'Right now, only fracas data is available'))

  argparser.add_argument(
      '--app',
      '-a',
      default=os.getenv('APP_ID', 'predator-for-me-staging'),
      help=('App id of the App engine app that query needs to access. '
            'Defualts to predator-for-me-staging. You can also set enviroment '
            'variable by \'export APP_ID=your-app-id\' to replace '
            'the default value.\nNOTE, only appspot app ids are supported, '
            'the app_id of googleplex app will have access issues '
            'due to internal proxy. '))

  argparser.add_argument(
      '--since',
      '-s',
      default=_A_YEAR_AGO,
      help=('Query data since this date (including this date). '
            'The date should be in YYYY-MM-DD format (e.g. 2015-09-31), '
            'defaults to a year ago.'))

  argparser.add_argument(
      '--until',
      '-u',
      default=_TODAY,
      help=('Query data until this date (not including this date). '
            'Should be in YYYY-MM-DD format (e.g. 2015-09-31), '
            'defaults to today.'))

  argparser.add_argument(
      '--batch',
      '-b',
      type=int,
      default=_DEFAULT_BATCH_SIZE,
      help=('The size of batch that can be processed at one time.\n'
            'NOTE, the batch size cannot be greater than 1000, or app engine '
            'APIs would fail, defaults to 1000.'))

  argparser.add_argument(
      '--max',
      '-m',
      type=int,
      default=_DEFAULT_MAX_N,
      help='The maximum number of crashes we want to check, defaults to 100.')

  argparser.add_argument(
      '--verbose',
      '-v',
      action='store_true',
      default=False,
      help='Print Predator results. Defaults to False.')

  args = argparser.parse_args()

  # If in verbose mode, prints debug information.
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)

  if len(args.revisions) > 2:
    logging.error('Only support delta test between 2 revisions.')
    sys.exit(1)

  if args.batch > _MAX_BATCH_SIZE:
    logging.error('Batch size cannot be greater than %s, or app engine APIs '
                  'would fail.', _MAX_BATCH_SIZE)
    sys.exit(1)

  args.batch = min(args.max, args.batch)

  # If only one revision provided, default the rev2 to HEAD.
  if len(args.revisions) == 1:
    args.revisions.append('HEAD')

  git_hash1 = delta_util.ParseGitHash(args.revisions[0])
  git_hash2 = delta_util.ParseGitHash(args.revisions[1])

  # Compute delta.
  deltas, triage_results, crash_num = delta_test.EvaluateDelta(
      git_hash1, git_hash2, args.client, args.app,
      args.since, args.until, args.batch, args.max,
      verbose=args.verbose)

  delta_csv_path = GenerateDeltaCSVPath(DELTA_RESULTS_DIRECTORY,
                                        git_hash1, git_hash2,
                                        args.since, args.until, args.max)
  delta_util.WriteDeltaToCSV(deltas, crash_num, args.client, args.app,
                             git_hash1, git_hash2, delta_csv_path,
                             triage_results=triage_results)

  # Print delta results to users.
  print '\n========================= Summary ========================='
  if args.verbose:
    delta_util.PrintDelta(deltas, crash_num, args.client, args.app)

  print 'Writing delta diff to %s\n' % delta_csv_path


if __name__ == '__main__':
  RunDeltaTest()
