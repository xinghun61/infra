# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import logging

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from common.crash_pipeline import RerunPipeline
from common.crash_pipeline import PredatorForClientID
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs import appengine_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.iterator import Iterate
from libs import time_util


RERUN_SERVICE = 'backend-process'
RERUN_QUEUE = 'rerun-queue'

DATETIME_FORMAT = '%Y-%m-%d'

CLIENT_ID_TO_CRASH_ANALYSIS = {
    CrashClient.FRACAS: FracasCrashAnalysis,
    CrashClient.CRACAS: CracasCrashAnalysis,
    CrashClient.CLUSTERFUZZ: ClusterfuzzAnalysis,
}

_BATCH_SIZE = 500


def IterateCrashBatches(client_id, start_date, end_date,
                        batch_size=_BATCH_SIZE):
  """Iterates and re-initializes crash analyses in [start_date, end_date).

  Args:
    client_id (CrashClient): The client whose crash we should iterate.
    start_date (datetime): Start date of the time range we iterate.
    end_date (datetime): End date of the time range we iterate
    batch_size (int): Size of the batch we iterate.
  """
  analysis = CLIENT_ID_TO_CRASH_ANALYSIS.get(client_id)

  query = analysis.query()
  query = query.filter(
      analysis.requested_time >= start_date).filter(
          analysis.requested_time < end_date)

  for crash_batch in Iterate(query, batch_size=batch_size, batch_run=True):
    yield [crash.key.urlsafe() for crash in crash_batch]


class RerunAnalyses(BaseHandler):
  """Rerun analysis on all crashes in a time range."""

  PERMISSION_LEVEL = Permission.ADMIN

  # TODO(crbug.com/731934): Add XSRF token verification.
  def HandleGet(self):
    client_id = self.request.get('client_id', CrashClient.CRACAS)

    now = time_util.GetUTCNow()
    last_week = time_util.GetUTCNow() - timedelta(days=7)

    start_date, end_date = time_util.GetStartEndDates(
        self.request.get('start_date'), self.request.get('end_date'),
        default_start=last_week, default_end=now)

    publish_to_client = bool(self.request.get('publish'))
    count = 0
    for crash_keys in IterateCrashBatches(client_id, start_date, end_date):
      pipeline = RerunPipeline(client_id, crash_keys, publish_to_client)
      # Attribute defined outside __init__ - pylint: disable=W0201
      pipeline.target = appengine_util.GetTargetNameForModule(RERUN_SERVICE)
      pipeline.start(queue_name=RERUN_QUEUE)
      count += 1

    if count == 0:
      message = 'No rerun pipeline started.'
    else:
      message = '%d rerun pipeline(s) kicked off.' % count

    return {'data': {'message': message}}
