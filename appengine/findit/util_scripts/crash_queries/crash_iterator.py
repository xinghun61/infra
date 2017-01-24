# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import date
from datetime import datetime
from datetime import timedelta

from crash.type_enums import CrashClient
import iterator
from libs.cache_decorator import GeneratorCached
from local_cache import LocalCache
from model.crash.cracas_crash_analysis import CracasCrashAnalysis
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

_DEFAULT_BATCH_SIZE = 1000
_TODAY = date.today().strftime('%Y-%m-%d')
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
_CLIENT_TO_ANALYSIS_CLASS = {CrashClient.FRACAS: FracasCrashAnalysis,
                             CrashClient.CRACAS: CracasCrashAnalysis}


# TODO(crbug.com/662540): Add unittests.
def GetQueryForClient(client_id, property_values, start_date, end_date,
                      datetime_pattern='%Y-%m-%d'):  # pragma: no cover.
  if property_values is None:
    property_values = {}

  start_date = datetime.strptime(start_date, datetime_pattern)
  end_date = datetime.strptime(end_date, datetime_pattern)
  cls = _CLIENT_TO_ANALYSIS_CLASS.get(client_id)
  if not cls:
    return None

  query = cls.query()
  for property_name, value in property_values.iteritems():
    query = query.filter(getattr(cls, property_name) == value)

  return query.filter(
      cls.requested_time >= start_date).filter(
      cls.requested_time < end_date)


# TODO(crbug.com/662540): Add unittests.
def IterateCrashes(client_id,
                   app_id,
                   fields=None,
                   property_values=None,
                   start_date=_A_YEAR_AGO,
                   end_date=_TODAY,
                   batch_size=_DEFAULT_BATCH_SIZE,
                   batch_run=False):  # pragma: no cover.
  """Genrates query to query crashes and iterates crashes.

  Args:
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS,
      CrashClient.CLUSTERFUZZ.
    app_id (str): App engine app id.
    fields (list): Field names of CrashAnalysis entity to project.
    property_values (dict): Property values to filter.
    start_date (str): Only iterate testcases after this date including this
      date, format '%Y-%m-%d'.
    end_date (str): Only iterate testcases before this date excluding this date,
      format '%Y-%m-%d'.
    batch_size (int): The number of crashes to query at one time.
    batch_run (bool): If True, iterate batches of crashes, if
      False, iterate each crash.

    An example is available in crash_printer/print_crash.py.
  """
  if property_values is None:
    property_values = {}

  query = GetQueryForClient(client_id, property_values, start_date, end_date)
  if not query:
    return

  for crash in iterator.Iterate(query, app_id, fields=fields,
                                batch_size=batch_size,
                                batch_run=batch_run):
    yield crash


@GeneratorCached(LocalCache(), namespace='Crash-iterator')  # pragma: no cover.
def CachedCrashIterator(client_id, app_id,
                        fields=None, property_values=None,
                        start_date=_A_YEAR_AGO, end_date=_TODAY,
                        batch_size=_DEFAULT_BATCH_SIZE, batch_run=False):
  """Genrates query to query crashes and iterates crashes.

  This iterator will check local cache first, if there is cache, iterate cached
  values, else it will visit datastore of appengine app to yield data.

  Args:
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS,
      CrashClient.CLUSTERFUZZ.
    app_id (str): App engine app id.
    fields (list): Field names of CrashAnalysis entity to project.
    property_values (dict): Property values to filter.
    start_date (str): Only iterate testcases after this date including this
      date, format '%Y-%m-%d'.
    end_date (str): Only iterate testcases before this date excluding this date,
      format '%Y-%m-%d'.
    batch_size (int): The number of crashes to query at one time.
    batch_run (bool): If True, iterate batches of crashes, if
      False, iterate each crash.

    An example is available in crash_printer/print_crash.py.
  """
  for crash in IterateCrashes(client_id, app_id, fields=fields,
                              property_values=property_values,
                              start_date=start_date, end_date=end_date,
                              batch_size=batch_size, batch_run=batch_run):
    yield crash
