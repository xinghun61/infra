# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import logging

from analysis.type_enums import CrashClient
from common.crash_pipeline import CrashWrapperPipeline
from common.crash_pipeline import RerunPipeline
from gae_libs import appengine_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util

RERUN_SERVICE = 'backend-process'
RERUN_QUEUE = 'rerun-queue'

DATETIME_FORMAT = '%Y-%m-%d'


class RerunAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    """Update crash analysis models."""
    client_id = self.request.get('client_id') or CrashClient.CRACAS

    now = time_util.GetUTCNow()
    yesterday = time_util.GetUTCNow() - timedelta(days=7)

    start_date = self.request.get('start_date')
    start_date = datetime.strptime(
        start_date, DATETIME_FORMAT) if start_date else yesterday

    end_date = self.request.get('end_date')
    end_date = datetime.strptime(
        end_date, DATETIME_FORMAT) if end_date else now

    pipeline = RerunPipeline(client_id, start_date, end_date)
    # Attribute defined outside __init__ - pylint: disable=W0201
    pipeline.target = appengine_util.GetTargetNameForModule(RERUN_SERVICE)
    pipeline.start(queue_name=RERUN_QUEUE)
