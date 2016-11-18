# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import pickle
import subprocess

from crash_queries import crash_iterator
from crash_queries.delta_test import delta_util

PREDATOR_RESULTS_DIRECTORY = os.path.join(os.path.dirname(__file__),
                                          'predator_results')
DELTA_TEST_DIRECTORY = os.path.dirname(__file__)
CRASH_FIELDS = ['crashed_version', 'stack_trace', 'signature',
                'platform', 'client_id', 'regression_range',
                'customized_data', 'historical_metadata']



# TODO(crbug.com/662540): Add unittests.
class Delta(object):  # pragma: no cover.
  """Stands for delta between two results.

  Note, the 2 results should be the same kind and have the same structure.
  """

  def __init__(self, result1, result2):
    self._result1 = result1
    self._result2 = result2
    self._delta_dict = None
    self._delta_str_dict = None

  @property
  def delta_dict(self):
    """Dict representation of delta.

    Returns:
    A dict. For example, for Culprit result, the delta dict is like below:
    {
        'project': 'chromium',
        'components': ['Blink>API'],
        'cls': [],
        'regression_range': ['52.0.1200.1', '52.0.1200.3']
    }
    """
    if self._delta_dict:
      return self._delta_dict

    self._delta_dict = {}
    result1 = self._result1.ToDicts()[0] if self._result1 else {'found': False}
    result2 = self._result2.ToDicts()[0] if self._result2 else {'found': False}
    keys = (set(result1.keys()) if result1 else set() |
            set(result2.keys()) if result2 else set())
    for key in keys:
      value1 = result1.get(key)
      value2 = result2.get(key)
      if value1 != value2:
        self._delta_dict[key] = (value1, value2)

    return self._delta_dict

  @property
  def delta_str_dict(self):
    """Converts delta of each field to a string."""
    if self._delta_str_dict:
      return self._delta_str_dict

    self._delta_str_dict = {}
    for key, (value1, value2) in self.delta_dict.iteritems():
      if key == 'suspected_cls':
        for value in [value1, value2]:
          if not value:
            continue

          for cl in value:
            cl['confidence'] = round(cl['confidence'], 2)
            cl.pop('reasons', None)

        value1 = json.dumps(value1, indent=4, sort_keys=True)
        value2 = json.dumps(value2, indent=4, sort_keys=True)

      self._delta_str_dict[key] = '%s 1: %s\n%s 2: %s\n' % (key, value1,
                                                            key, value2)

    return self._delta_str_dict

  def ToDict(self):
    return self.delta_dict

  def __str__(self):
    return '\n'.join(self.delta_str_dict.values())

  def __bool__(self):
    return bool(self.delta_dict)

  def __nonzero__(self):
    return self.__bool__()


# TODO(crbug.com/662540): Add unittests.
def GetDeltasFromTwoSetsOfResults(set1, set2):  # pragma: no cover.
  """Gets delta from two sets of results.

  Set1 and set2 are dicts mapping id to result.
  Results are a list of (message, matches, component_name, cr_label)
  Returns a list of delta results (results1, results2).
  """
  deltas = {}
  for result_id, result1 in set1.iteritems():
    # Even when the command are exactly the same, it's possible that one set is
    # loaded from local result file, another is just queried from database,
    # sometimes some crash results would get deleted.
    if result_id not in set2:
      continue

    result2 = set2[result_id]
    if not result1 and not result2:
      continue

    delta = Delta(result1, result2)
    if delta:
      deltas[result_id] = delta

  return deltas


# TODO(crbug.com/662540): Add unittests.
def GetResults(crashes, client_id, app_id, git_hash, result_path,
               verbose=False):  # pragma: no cover.
  """Returns an evaluator function to compute delta between 2 findit githashes.

  Args:
    crashes (list): A list of crash infos.
    client_id (str): Possible values - fracas/cracas/clustefuzz.
    app_id (str): Appengine app id to query.
    git_hash (str): A git hash of findit repository.
    result_path (str): file path for subprocess to write results on.
    verbose (bool): If True, print all the findit results.

  Return:
    A dict mapping crash id to culprit for every crashes analyzed by
    git_hash version.
  """
  if not crashes:
    return {}

  print '***************************'
  print 'Switching to git %s' % git_hash
  print '***************************'
  with open(os.devnull, 'w') as null_handle:
    subprocess.check_call(
        'cd %s; git checkout %s' % (DELTA_TEST_DIRECTORY, git_hash),
        stdout=null_handle,
        stderr=null_handle,
        shell=True)

  if not os.path.exists(result_path):
    args = ['python', 'run-predator.py', result_path, client_id, app_id]
    if verbose:
      args.append('--verbose')
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    # TODO(katesonia): Cache crashes for crash_iterator and let subprocess read
    # corresponding cache file instead.
    p.communicate(input=json.dumps(crashes))
  else:
    print '\nLoading results from', result_path

  if not os.path.exists(result_path):
    print 'Failed to get results.'
    return {}

  with open(result_path) as f:
    return pickle.load(f)

  return {}


# TODO(crbug.com/662540): Add unittests.
def DeltaEvaluator(git_hash1, git_hash2,
                   client_id, app_id,
                   start_date, end_date, batch_size,
                   property_values=None, verbose=False):  # pragma: no cover.
  """Evaluates delta between git_hash1 and git_hash2 on a set of Testcases.

  Args:
    git_hash1 (str): A git hash of findit repository.
    git_hash2 (str): A git hash of findit repository.
    start_date (str): Run delta test on testcases after (including)
      the start_date, format should be '%Y-%m-%d'.
    end_date (str): Run delta test on testcases before (not including)
      the end_date, format should be '%Y-%m-%d'.
    client_id (CrashClient): Possible values are 'fracas', 'cracas',
      'cluterfuzz'.
    app_id (str): Appengine app id to query.
    batch_size (int): Size of a batch that can be queried at one time.
    property_values (dict): Property values to query.
       batch_size (int): The size of crashes that can be queried at one time.
    verbose (bool): If True, print all the findit results.
  Return:
    (deltas, crash_count).
    deltas (dict): Mappings id to delta for each culprit value.
    crash_count (int): Total count of all the crashes.
  """
  head_branch_name = subprocess.check_output(
      ['git', 'rev-parse', '--abbrev-ref', 'HEAD']).replace('\n', '')
  try:
    deltas = {}
    crash_count = 0
    for index, crashes in enumerate(
        crash_iterator.IterateCrashes(client_id, app_id,
                                      fields=CRASH_FIELDS,
                                      property_values=property_values,
                                      start_date=start_date,
                                      end_date=end_date,
                                      batch_size=batch_size,
                                      batch_run=True)):

      results = []
      for git_hash in [git_hash1, git_hash2]:
        result_path = os.path.join(
            PREDATOR_RESULTS_DIRECTORY, delta_util.GenerateFileName(
                client_id, property_values, start_date, end_date,
                batch_size, index, git_hash))
        results.append(GetResults(crashes, client_id, app_id,
                                  git_hash, result_path,
                                  verbose=verbose))

      crash_count += len(crashes)
      batch_deltas = GetDeltasFromTwoSetsOfResults(*results)
      # Print deltas of the current batch.
      print '========= Delta of this batch ========='
      delta_util.PrintDelta(batch_deltas, len(crashes), app_id)
      deltas.update(batch_deltas)

    return deltas, crash_count
  finally:
    with open(os.devnull, 'w') as null_handle:
      subprocess.check_call(['git', 'checkout', head_branch_name],
                            stdout=null_handle,
                            stderr=null_handle)
