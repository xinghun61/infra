# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is used to obscure recorded emails."""

from datetime import timedelta

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler, Permission
from libs import email_util
from libs import time_util
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_analysis import WfAnalysis

_TRIAGE_RECORD_RENTENSION_DAYS = 30  # 1 month.
_REQUEST_RECORD_RENTENSION_DAYS = 90  # 3 months.
_PAGE_SIZE = 100  # Query 100 entities at a time.


def _TimeBeforeNow(days=0):
  return time_util.GetUTCNow() - timedelta(days=days)


def _ObscureTriageRecordsInWfAnalysis():
  """Obscures the user names in WfAnalysis triage history."""
  count = 0
  time_limit = _TimeBeforeNow(days=_TRIAGE_RECORD_RENTENSION_DAYS)
  query = WfAnalysis.query(WfAnalysis.triage_email_obscured == False,
                           WfAnalysis.triage_record_last_add < time_limit)
  more = True
  cursor = None
  while more:
    entities, cursor, more = query.fetch_page(_PAGE_SIZE, start_cursor=cursor)
    for entity in entities:
      for triage_record in (entity.triage_history or []):
        triage_record['user_name'] = email_util.ObscureEmails(
            [triage_record['user_name']], ['google.com'])[0]
      entity.triage_email_obscured = True
    ndb.put_multi(entities)
    count += len(entities)
  return count


def _ObscureTriageRecordsInMasterFlakeAnalysis():
  """Obscures the user names in MasterFlakeAnalysis triage history."""
  count = 0
  time_limit = _TimeBeforeNow(days=_TRIAGE_RECORD_RENTENSION_DAYS)
  query = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.triage_email_obscured == False,
      MasterFlakeAnalysis.triage_record_last_add < time_limit)
  more = True
  cursor = None
  while more:
    entities, cursor, more = query.fetch_page(_PAGE_SIZE, start_cursor=cursor)
    for entity in entities:
      for triage_record in (entity.triage_history or []):
        triage_record.user_name = email_util.ObscureEmails(
            [triage_record.user_name], ['google.com'])[0]
      entity.triage_email_obscured = True
    ndb.put_multi(entities)
    count += len(entities)
  return count


def _ObscureFlakeAnalysisRequest():
  """Obscures the user emails in FlakeAnalysisRequest."""
  count = 0
  time_limit = _TimeBeforeNow(days=_REQUEST_RECORD_RENTENSION_DAYS)
  query = FlakeAnalysisRequest.query(
      FlakeAnalysisRequest.user_emails_obscured == False,
      FlakeAnalysisRequest.user_emails_last_edit < time_limit)
  more = True
  cursor = None
  while more:
    entities, cursor, more = query.fetch_page(_PAGE_SIZE, start_cursor=cursor)
    for entity in entities:
      entity.user_emails = email_util.ObscureEmails(entity.user_emails,
                                                    ['google.com'])
      entity.user_emails_obscured = True
    ndb.put_multi(entities)
    count += len(entities)
  return count


def _ObscureMasterFlakeAnalysis():
  """Obscures the user email in MasterFlakeAnalysis."""
  count = 0
  time_limit = _TimeBeforeNow(days=_REQUEST_RECORD_RENTENSION_DAYS)
  query = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.triggering_user_email_obscured == False,
      MasterFlakeAnalysis.request_time < time_limit)
  more = True
  cursor = None
  while more:
    entities, cursor, more = query.fetch_page(_PAGE_SIZE, start_cursor=cursor)
    for entity in entities:
      entity.triggering_user_email = email_util.ObscureEmails(
          [entity.triggering_user_email], ['google.com'])[0]
      entity.triggering_user_email_obscured = True
    ndb.put_multi(entities)
    count += len(entities)
  return count


class ObscureEmails(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    """Obscures emails according to data retention policy."""
    failure_triage_count = _ObscureTriageRecordsInWfAnalysis()
    flake_triage_count = _ObscureTriageRecordsInMasterFlakeAnalysis()
    flake_request_aggregated_count = _ObscureFlakeAnalysisRequest()
    flake_request_count = _ObscureMasterFlakeAnalysis()
    return {
        'data': {
            'failure_triage_count': failure_triage_count,
            'flake_triage_count': flake_triage_count,
            'flake_request_aggregated_count': flake_request_aggregated_count,
            'flake_request_count': flake_request_count,
        }
    }
