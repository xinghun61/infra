# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

_ROOT_DIR = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), os.path.pardir, os.path.pardir)
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)
from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from scripts import setup
from scripts.testset.testset_updator import TestsetUpdator

_DEFAULT_MAX_N = 500


if __name__ == '__main__':
  argparser = argparse.ArgumentParser(
      description='Crawl data from datastore and dump it to testset.')

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
            'fracas is supported.'))

  argparser.add_argument(
      '--app',
      '-a',
      default=setup.DEFAULT_APP_ID,
      help=('App id of the App engine app that query needs to access. '
            'Defaults to \'%s\'.') % setup.DEFAULT_APP_ID)

  argparser.add_argument(
      '--with-culprit',
      dest='culprit',
      default='culprit_cls',
      help=('Crawl data with triaged culprit results - (culprit_cls, '
            'culprit_components, culprit_regression_range) '
            'to crawl test data.'))

  argparser.add_argument(
      '--output-testset',
      dest='testset',
      default=None,
      help=('Path to store the dumped testset.'))

  argparser.add_argument(
      '--max',
      '-m',
      type=int,
      default=_DEFAULT_MAX_N,
      help=('Maximum size of test data.'))

  args = argparser.parse_args()

  if args.testset is None:
    data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
    if not os.path.exists(data_dir):
      os.makedirs(data_dir)

    # Default testset path if testset path is not specified explicitly.
    testset_path = os.path.join(data_dir, '%s_testset.%s' % (args.client,
                                                             args.culprit))
  else:
    testset_path = args.testset

  TestsetUpdator(args.client, args.app,
                 culprit_property=args.culprit,
                 start_date=args.since, end_date=args.until,
                 testset_path=testset_path, max_n=args.max)
