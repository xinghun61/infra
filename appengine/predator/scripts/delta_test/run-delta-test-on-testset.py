# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs delta test on two Predator revisions."""

import argparse
from datetime import date
from datetime import timedelta
import hashlib
import logging
import os
import pickle
import sys

_ROOT_DIR = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), os.path.pardir)
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)

from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from scripts.delta_test import delta_util
from scripts.delta_test.delta_test import EvaluateDeltaOnTestSet

DELTA_RESULTS_DIRECTORY = os.path.join(os.path.dirname(__file__),
                                       'delta_results')


def GenerateDeltaCSVPath(directory, git_hash1, git_hash2, client_id,
                         testset_path):
  """Returns the file path of delta result."""
  delta_result_prefix = '%s_%s_%s_%s.delta.csv' % (
      client_id, git_hash1[:7], git_hash2[:7],
      hashlib.md5(testset_path).hexdigest())

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

  argparser.add_argument('testset',
                         help='The path to testset to run delta test on.')

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
      default='cracas',
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
    logging.error('Delta test can compare at most two revisions.')
    sys.exit(1)

  # If only one revision provided, default the rev2 to HEAD.
  if len(args.revisions) == 1:
    args.revisions.append('HEAD')

  git_hash1 = delta_util.ParseGitHash(args.revisions[0])
  git_hash2 = delta_util.ParseGitHash(args.revisions[1])

  testset_path = os.path.realpath(args.testset)
  deltas, triage_results, crash_num = EvaluateDeltaOnTestSet(
      git_hash1, git_hash2, args.client, args.app,
      testset_path, verbose=args.verbose)

  delta_csv_path = GenerateDeltaCSVPath(DELTA_RESULTS_DIRECTORY,
                                        git_hash1, git_hash2,
                                        args.client, testset_path)
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
