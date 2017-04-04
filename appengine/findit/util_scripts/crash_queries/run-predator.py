# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import os
import pickle
import sys
import threading
import traceback
import zlib

_CRASH_QUERIES_DIR = os.path.dirname(os.path.realpath(__file__))
_SCRIPT_DIR = os.path.join(_CRASH_QUERIES_DIR, os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)

import remote_api
import script_util
script_util.SetUpSystemPaths()

from google.appengine.ext import ndb

from crash_queries.run_predator import GetCulprits

PREDATOR_RESULTS_DIRECTORY = os.path.join(_CRASH_QUERIES_DIR,
                                          'predator_results')
try:
  os.makedirs(PREDATOR_RESULTS_DIRECTORY)
except Exception:
  pass


def RunPredator():
  """Runs delta testing between 2 different Findit versions."""
  argparser = argparse.ArgumentParser(
      description='Run Predator on a batch of crashes.')

  argparser.add_argument(
      '--input-path',
      dest='input_path',
      default=None,
      help='Path to read a list of ``CrashAnalysis`` entities')

  argparser.add_argument(
      '--result-path',
      dest='result_path',
      default=None,
      help='Path to store results')

  argparser.add_argument(
      '--key',
      '-k',
      default=None,
      help='Key to a single crash.')

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
      help='Print Predator results.')
  args = argparser.parse_args()

  if args.input_path:
    with open(args.input_path) as f:
      crashes = pickle.loads(zlib.decompress(f.read()))
  elif args.key:
    remote_api.EnableRemoteApi(app_id=args.app)
    crashes = {args.key: ndb.Key(urlsafe=args.key).get()}

  if not crashes:
    logging.error('Failed to get crashes info.')
    return

  culprits = GetCulprits(crashes, args.client, args.app, args.verbose)

  if args.result_path:
    script_util.FlushResult(culprits, args.result_path)


if __name__ == '__main__':
  # Disable the trivial loggings inside predator.
  logging.basicConfig(level=logging.ERROR)
  RunPredator()
