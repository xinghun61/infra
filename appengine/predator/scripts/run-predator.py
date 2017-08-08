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

_ROOT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
_ROOT_APP_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir, 'app')
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)
sys.path.insert(1, _ROOT_APP_DIR)

from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from local_libs import remote_api

from google.appengine.ext import ndb

from scripts.run_predator import GetCulprits
from scripts.run_predator import PREDATOR_RESULTS_DIRECTORY
from scripts import setup

try:
  os.makedirs(PREDATOR_RESULTS_DIRECTORY)
except Exception:
  pass


def RunPredator():
  """Runs delta testing between 2 different Predator versions."""
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
      help='Key to one single crash.')

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
      default=setup.DEFAULT_APP_ID,
      help=('App id of the App engine app that query needs to access. '
            'Defaults to \'%s\'. NOTE, only appspot app ids are supported, '
            'the app_id of googleplex app will have access issues '
            'due to internal proxy. ') % setup.DEFAULT_APP_ID)

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
