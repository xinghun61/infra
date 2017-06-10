# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import date
from datetime import timedelta
import os
import sys

_ROOT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         os.path.pardir)
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)

from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from analysis.type_enums import CrashClient
from libs.cache_decorator import GeneratorCached
from local_libs import local_iterator
from local_libs.local_cache import LocalCache
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.fracas_crash_analysis import FracasCrashAnalysis

_DEFAULT_BATCH_SIZE = 1000
_TODAY = date.today().strftime('%Y-%m-%d')
_A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
_CLIENT_ID_TO_CLASS = {CrashClient.FRACAS: FracasCrashAnalysis,
                       CrashClient.CRACAS: CracasCrashAnalysis,
                       CrashClient.CLUSTERFUZZ: ClusterfuzzAnalysis}


# TODO(crbug.com/662540): Add unittests.
def IterateCrashes(client_id,
                   app_id,
                   projection=None,
                   property_values=None,
                   start_date=_A_YEAR_AGO,
                   end_date=_TODAY,
                   batch_size=_DEFAULT_BATCH_SIZE,
                   batch_run=False):  # pragma: no cover.
  """Genrates query to query crashes and iterates crashes.

  Args:
    client_id (CrashClient): One of the 3 supported clients -
      CrashClient.FRACAS, CrashClient.CRACAS and CrashClient.CLUSTERFUZZ.
    app_id (str): App engine app id.
    projection (tuple or list): Operations return entities with only the
      specified properties set. For example:
      projection=[Article.title, Article.date] or
      projection=['title', 'date'] fetches entities with just those two
      fields set. Note, query can only project indexed properties.
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
  cls = _CLIENT_ID_TO_CLASS.get(client_id)
  if property_values:
    property_values = {getattr(cls, property_name): value for
                       property_name, value in property_values.iteritems()}

  query = script_util.GetFilterQuery(
      cls.query(), cls.requested_time, start_date, end_date,
      property_values=property_values)

  # According to https://goo.gl/5BgxQt, the query must be sorted by key
  # to make a query with both ``IN`` operation and cursor.
  query = query.order(-cls.requested_time, cls.key)
  for crash in local_iterator.ScriptIterate(
      query, app_id, projection=projection,
      batch_size=batch_size, batch_run=batch_run):
    yield crash


@GeneratorCached(LocalCache(), namespace='Crash-iterator')  # pragma: no cover.
def CachedCrashIterator(client_id, app_id,
                        projection=None,
                        property_values=None,
                        start_date=_A_YEAR_AGO, end_date=_TODAY,
                        batch_size=_DEFAULT_BATCH_SIZE, batch_run=False):
  """Genrates query to query crashes and iterates crashes.

  This iterator will check local cache first, if there is cache, iterate cached
  values, else it will visit datastore of appengine app to yield data.

  Args:
    client_id (CrashClient): One of the 3 supported clients -
      CrashClient.FRACAS, CrashClient.CRACAS and CrashClient.CLUSTERFUZZ.
    app_id (str): App engine app id.
    projection (tuple or list): Operations return entities with only the
      specified properties set. For example:
      projection=[Article.title, Article.date] or
      projection=['title', 'date'] fetches entities with just those two
      fields set. Note, query can only project indexed properties.
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
  for crash in IterateCrashes(client_id, app_id, projection=projection,
                              property_values=property_values,
                              start_date=start_date, end_date=end_date,
                              batch_size=batch_size, batch_run=batch_run):
    yield crash
