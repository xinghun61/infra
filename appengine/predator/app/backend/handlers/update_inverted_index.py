# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handler to update inverted index so we can compute idf for each keyword."""

from datetime import datetime
from datetime import timedelta
import json
import logging
import traceback

from google.appengine.ext import ndb

from analysis.keyword_extractor import FilePathExtractor
from analysis.type_enums import CrashClient
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from common.model.inverted_index import ClusterfuzzInvertedIndex
from common.model.inverted_index import ChromeCrashInvertedIndex
from common.model.inverted_index import InvertedIndex
from gae_libs.handlers.base_handler import BaseHandler, Permission
from libs import time_util

CRASH_ANALYSIS_TO_INVERTED_INDEX = {
    FracasCrashAnalysis: ChromeCrashInvertedIndex,
    ClusterfuzzAnalysis: ClusterfuzzInvertedIndex
}


def UpdateInvertedIndexForCrash(crash_report, keyword_extractor,
                                inverted_index_model=None):
  """Updates all inverted index of keywords in a single crash.

  Args:
    crash_report (CrashReport): The crash report with all needed crash infos.
    keyword_extractor (KeywordExtractor): Extractor to extract keywords from a
    crash report.
    inverted_index_model (InvertedIndex): The model to compute inverted index.
  """
  keywords = keyword_extractor(crash_report)
  update_list = []
  inverted_index_model = inverted_index_model or InvertedIndex

  logging.info('for crash %s', crash_report.signature)
  logging.info('keywords: %s', json.dumps(keywords))
  for keyword in keywords:
    inverted_index = (inverted_index_model.Get(keyword) or
                      inverted_index_model.Create(keyword))
    inverted_index.n_of_doc += 1
    update_list.append(inverted_index)

  root = inverted_index_model.GetRoot()
  root.n_of_doc += 1
  update_list.append(root)

  ndb.put_multi(update_list)


class UpdateInvertedIndex(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    """Updates all inverted index for all crashes in last day."""
    for crash_analysis_model, inverted_index_model in (
        CRASH_ANALYSIS_TO_INVERTED_INDEX.iteritems()):

      today = time_util.GetUTCNow()
      yesterday = today - timedelta(days=1)
      query = crash_analysis_model.query(ndb.AND(
          crash_analysis_model.requested_time >= yesterday,
          crash_analysis_model.requested_time < today))

      crash_analyses = query.fetch()
      for crash_analysis in crash_analyses:
        # Updates the ``InvertedIndex`` (file path to the number of stacktraces
        # which contains this file path) for every file path in all stacktraces
        # within the time range.
        UpdateInvertedIndexForCrash(
            crash_analysis.ToCrashReport(),
            FilePathExtractor(),
            inverted_index_model=inverted_index_model)

      logging.info('Finished updating %s with %d crashes',
                   crash_analysis_model.__class__.__name__, len(crash_analyses))
