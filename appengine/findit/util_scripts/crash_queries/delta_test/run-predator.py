# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import os
import sys
import threading
import traceback

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
from model.crash.crash_config import CrashConfig
import remote_api

_FRACAS_FEEDBACK_URL_TEMPLATE = (
    'https://%s.appspot.com/crash/fracas-result-feedback?key=%s')


def StoreResults(crash, client_id, app_id, id_to_culprits, lock, verbose=False):
  """Stores findit result of crash into id_to_culprits dict."""
  crash_url = _FRACAS_FEEDBACK_URL_TEMPLATE % (app_id, crash['id'])
  try:
    findit = FinditForClientID(client_id, LocalGitRepository)
    stacktrace = findit._stacktrace_parser.Parse(
        crash['stack_trace'],
        ChromeDependencyFetcher(LocalGitRepository.Factory()).GetDependency(
            crash['crashed_version'],
            crash['platform']))
    if stacktrace:
      culprit = findit._predator.FindCulprit(CrashReport(
          crashed_version=crash['crashed_version'],
          signature=crash['signature'],
          platform=crash['platform'],
          stacktrace=stacktrace,
          regression_range=crash['regression_range']))
    else:
      culprit = None
    with lock:
      id_to_culprits[crash['id']] = culprit
      if verbose:
        print '\n\nCrash:', crash_url
        print json.dumps(culprit.ToDicts()[0] if culprit else {'found': False},
                         indent=4, sort_keys=True)
  except Exception:
    with lock:
      id_to_culprits[crash['id']] = None
      print '\n\nCrash:', crash_url
      print traceback.format_exc()


def GetCulprits(crashes, client_id, app_id, verbose=False):
  """Run predator analysis on crashes locally."""
  # Enable remote access to app engine services.
  remote_api.EnableRemoteApi(app_id)
  origin_get = CrashConfig.Get
  try:
    # This hack is to solve flaky BadStatusLine excepion(crbug.com/666150) in
    # remote api when key.get() gets called in threads.
    # TODO(katesonia): Remove this hack after crbug.com/659354 is done.
    CrashConfig.Get = script_util.GetLockedMethod(CrashConfig, 'Get',
                                                  threading.Lock())
    id_to_culprits = {}
    tasks = []
    lock = threading.Lock()
    for crash in crashes:
      crash['regression_range'] = DetectRegressionRange(
          crash['historical_metadata'])
      tasks.append({
          'function': StoreResults,
          'args': [crash, client_id, app_id, id_to_culprits, lock],
          'kwargs': {'verbose': verbose}
      })
    script_util.RunTasks(tasks)

    return id_to_culprits
  finally:
    CrashConfig.Get = origin_get


def RunPredator():
  """Runs delta testing between 2 different Findit versions."""
  argparser = argparse.ArgumentParser(
      description='Run Predator on a batch of crashes.')
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
      help='Print findit results.')
  args = argparser.parse_args()

  crashes = json.loads(raw_input())
  if not crashes:
    logging.error('Failed to get crashes info.')
    return

  culprits = GetCulprits(crashes, args.client, args.app, args.verbose)
  delta_util.FlushResult(culprits, args.result_path)


if __name__ == '__main__':
  # Disable the trivial loggings inside predator.
  logging.basicConfig(level=logging.ERROR)
  RunPredator()
