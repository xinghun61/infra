# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import date
from datetime import datetime
from datetime import timedelta

from crash.type_enums import CrashClient
import iterator
from model.crash.cracas_crash_analysis import CracasCrashAnalysis
from model.crash.fracas_crash_analysis import FracasCrashAnalysis
import remote_api

_DEFAULT_BATCH_SIZE = 1000
_TODAY = date.today().strftime('%Y-%m-%d')
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')

COMMON_CRASH_FIELDS = ['crashed_version', 'stack_trace', 'signature',
                       'platform', 'client_id', 'customized_data']


# TODO(katesonia): Switch to use fuction of objects encapsulating CrashClients,
# after the refactoring is done.
def GetAnalysisClassForClient(client_id):
  if client_id == CrashClient.FRACAS:
    return FracasCrashAnalysis
  elif client_id == CrashClient.CRACAS:
    return CracasCrashAnalysis
  elif client_id == CrashClient.CLUSTERFUZZ:
    # TODO(katesonia): Define ClusterfuzzCrashAnalysis.
    return None

  return None


def GetQueryForClient(client_id, property_values, start_date, end_date,
                      datetime_pattern='%Y-%m-%d'):
  if property_values is None:
    property_values = {}

  start_date = datetime.strptime(start_date, datetime_pattern)
  end_date = datetime.strptime(end_date, datetime_pattern)
  cls = GetAnalysisClassForClient(client_id)
  query = cls.query()
  for property_name, value in property_values.iteritems():
    query = query.filter(getattr(cls, property_name) == value)

  return query.filter(
      cls.requested_time >= start_date).filter(
      cls.requested_time < end_date)


def IterateCrashes(client_id,
                   app_id,
                   fields=None,
                   property_values=None,
                   start_date=_A_YEAR_AGO,
                   end_date=_TODAY,
                   batch_size=_DEFAULT_BATCH_SIZE,
                   batch_run=False):
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
  if fields is None:
    fields = COMMON_CRASH_FIELDS

  if property_values is None:
    property_values = {}

  query = GetQueryForClient(client_id, property_values, start_date, end_date)
  for crash in iterator.Iterate(query, fields, app_id, batch_size=batch_size,
                                batch_run=batch_run):
    yield crash
