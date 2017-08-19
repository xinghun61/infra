# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import os
import pickle
import sys
import zlib

_ROOT_DIR = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), os.path.pardir, os.path.pardir)
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)
from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from analysis.type_enums import CrashClient
from scripts import crash_iterator
from app.common.model import triage_status

_FEEDBACK_URL_TEMPLATE = (
    'https://%s.appspot.com/%s/result-feedback?key=%s')

_CULPRIT_TO_TRIAGE_PROPERTY = {
    'culprit_cls': 'suspected_cls_triage_status',
    'culprit_regression_range': 'regression_range_triage_status'
}


def WriteTestsetToCSV(testset_csv_path, test_set, app_id):
  """Writes ``test_set`` to a csv in ``testset_csv_path``."""

  with open(testset_csv_path, 'wb') as f:
    f.write('Crash, Culprit cl, Culprit components\n')
    for crash in test_set.itervalues():
      feedback_url = _FEEDBACK_URL_TEMPLATE % (
          app_id, crash.client_id, crash.key.urlsafe())

      culprit_components = crash.culprit_components or ''
      if isinstance(culprit_components, basestring):
        culprit_components = culprit_components.split('\n')

      culprit_components = ', '.join(culprit_components)
      f.write('"%s", "%s", "%s"\n' %  (
          feedback_url,
          '\n'.join(crash.culprit_cls) if crash.culprit_cls else '',
          culprit_components))


def _PropertyValuesToQueryTriagedData(culprit_property):
  """Gets the property values to query triaged data for ``culprit_property``.

  Args:
    culprit_property (str): one of 3 culprit properties - ``culprit_cls``,
      ``culprit_regression_range``, ``culprit_components``.

  Returns:
    A dict mapping triage status property to its triage status.
    For example:
      {
          'culprit_cls': ['Correct', 'Incorrect']
      }
  """
  if culprit_property is None:
    property_values = None
  else:
    triage_property = _CULPRIT_TO_TRIAGE_PROPERTY.get(culprit_property)
    property_values = {triage_property: [triage_status.TRIAGED_CORRECT,
                                         triage_status.TRIAGED_INCORRECT]}
  return property_values


def _PropertyValuesToQueryUntriagedData():
  """Gets the property values to query un-triaged data for ``culprit_property``.

  Returns:
    A dict mapping triage status property to its triage status.
    For example:
      {
          'culprit_cls': 'Untriaged',
          'culprit_regression_range': 'Untriaged'
      }
  """
  property_values = {}
  for triage_property in _CULPRIT_TO_TRIAGE_PROPERTY.itervalues():
    property_values[triage_property] = triage_status.UNTRIAGED

  return property_values


def _DumpTestSet(test_set, testset_path, app_id):
  """Dumps ``test_set`` to ``testset_path``."""
  # TODO(katesonia): Upload it to cloud storage as well.
  with open(testset_path, 'wb') as f:
    f.write(zlib.compress(pickle.dumps(test_set)))

  testset_csv_path = testset_path + '.csv'
  WriteTestsetToCSV(testset_csv_path, test_set, app_id)
  print 'Dump %d crashes into testset - %s' % (len(test_set),
                                               testset_csv_path)


def TestsetUpdator(client_id, app_id, culprit_property=None,
                   start_date=None, end_date=None,
                   testset_path='testset', max_n=500):
  """Crawls data and dump it to the testset.

  Args:
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS,
      CrashClient.CLUSTERFUZZ.
    app_id (str): The project id of app engine app to query data frome.
    culprit_property (str): one of 3 culprit properties - ``culprit_cls``,
      ``culprit_regression_range``, ``culprit_components``.
    start_date (str): The start date of the time range to query data from, in
      format '%Y-%m-%d', for example, '2017-03-01'.
    end_date (str):  The end date of the time range to query data from, in
      format '%Y-%m-%d', for example, '2017-03-01'.
    testset_path (str): The local path to dump testset data to.
    max_n (int): The maximum number of crashes to create the testset.
  """
  print 'Crawling the test data...'

  test_set = {}
  # First query all triaged data of ``culprit_property`` in the time range.
  # Then, if the triaged data is not enough, query untriaged data to meet
  # ``max_n``.
  get_property_funcs = [
      functools.partial(_PropertyValuesToQueryTriagedData, culprit_property),
      _PropertyValuesToQueryUntriagedData]

  for get_property_func in get_property_funcs:
    property_values = get_property_func()
    for crash in crash_iterator.CachedCrashIterator(
        client_id, app_id, property_values=property_values,
        start_date=start_date, end_date=end_date):
      if len(test_set) >= max_n:
        break

      crash.culprit_cls = (''.join(crash.culprit_cls).split(',') if
                           crash.culprit_cls else None)
      test_set[crash.key.urlsafe()] = crash

  if test_set:
    _DumpTestSet(test_set, testset_path, app_id)
  else:
    print 'There is no data with %s' % culprit_property
