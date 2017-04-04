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

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                           os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)

import script_util
script_util.SetUpSystemPaths()

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from crash.crash_pipeline import FinditForClientID
from crash.crash_report import CrashReport
from crash.culprit import Culprit
from crash.detect_regression_range import DetectRegressionRange
from crash.findit_for_chromecrash import FinditForChromeCrash
from crash.type_enums import CrashClient
from crash_queries.delta_test import delta_util
from git_checkout.local_git_repository import LocalGitRepository
from model.crash import crash_analysis
from model.crash.crash_config import CrashConfig
import remote_api


def StoreResults(crash, client_id, app_id, id_to_culprits, lock, config,
                 verbose=False):
  """Stores predator result of crash into id_to_culprits dict."""
  crash_id = crash.key.urlsafe()
  feedback_url = crash_analysis._FEEDBACK_URL_TEMPLATE % (
      app_id, client_id, crash_id)
  try:
    findit = FinditForClientID(client_id, LocalGitRepository, config)
    culprit = findit.FindCulprit(crash.ToCrashReport())
    with lock:
      id_to_culprits[crash_id] = culprit
      if verbose:
        print '\n\nCrash:', feedback_url
        print json.dumps(culprit.ToDicts()[0] if culprit else {'found': False},
                         indent=4, sort_keys=True)
  except Exception:
    with lock:
      id_to_culprits[crash_id] = None
      print '\n\nCrash:', feedback_url
      print traceback.format_exc()


def GetCulprits(crashes, client_id, app_id, verbose=False):
  """Run ``CrashAnalysis`` entities in parallel and returns culprits.

  Args:
    crashes (list): A list of ``CrashAnalysis`` entities to run Predator on and
      get culprit results.
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS and
      CrashClient.CLUSTERFUZZ.
    app_id (str): Project id of app engine app.
    verbose (boolean): Whether to print every culprit results or not.

  Returns:
    A dict mapping crash id (urlsafe of entity key for Cracas/Fracas, testcase
    id for Cluterfuzz) to culprit results (dict version of ``Culprit``.)
  """
  # Enable remote access to app engine services.
  remote_api.EnableRemoteApi(app_id)

  tasks = []
  lock = threading.Lock()
  config = CrashConfig.Get()
  id_to_culprits = {}
  for crash in crashes:
    tasks.append({
        'function': StoreResults,
        'args': [crash, client_id, app_id, id_to_culprits, lock, config],
        'kwargs': {'verbose': verbose}
    })
  script_util.RunTasks(tasks)

  return id_to_culprits


def RunPredator():
  """Runs delta testing between 2 different Findit versions."""
  argparser = argparse.ArgumentParser(
      description='Run Predator on a batch of crashes.')
  argparser.add_argument('input_path', help='Path to read a list of '
                         '``CrashAnalysis`` entities')
  argparser.add_argument('result_path', help='Path to store results')
  argparser.add_argument('client', help=('Possible values are: fracas, cracas, '
                                         'clusterfuzz. Right now, only fracas '
                                         'is supported.'))
  argparser.add_argument('app', help='App engine id to get config from.')
  argparser.add_argument(
      '--verbose',
      '-v',
      action='store_true',
      default=False,
      help='Print Predator results.')
  args = argparser.parse_args()

  with open(args.input_path) as f:
    crashes = pickle.loads(zlib.decompress(f.read()))

  if not crashes:
    logging.error('Failed to get crashes info.')
    return

  culprits = GetCulprits(crashes, args.client, args.app, args.verbose)
  delta_util.FlushResult(culprits, args.result_path)


if __name__ == '__main__':
  # Disable the trivial loggings inside predator.
  logging.basicConfig(level=logging.ERROR)
  RunPredator()
