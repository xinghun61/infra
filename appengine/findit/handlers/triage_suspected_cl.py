# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to handle manual triage of a suspected CL.

This handler will flag the suspected cl as correct or incorrect.
"""

from google.appengine.api import users
from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model import result_status
from model import suspected_cl_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_util
from waterfall import buildbot
from waterfall.suspected_cl_util import GetCLInfo


@ndb.transactional
def _UpdateSuspectedCL(
    repo_name, revision, build_key, cl_status, updated_time=None):
  suspected_cl = WfSuspectedCL.Get(repo_name, revision)
  if (not suspected_cl or not suspected_cl.builds):
    return False

  if not suspected_cl.builds.get(build_key):
    # The failure is not a first time failure.
    # Will not update suspected_cl but will update analysis.
    return True

  suspected_cl.builds[build_key]['status'] = cl_status

  cl_correct = True
  cl_incorrect = True
  partial_triaged = False
  # Checks if all the builds have been triaged and checks the status of the cl
  # on each build.
  # If all the builds are  correct, the cl is correct;
  # If all the builds are incorrect, the cl is incorrect;
  # If some builds are correct while others aren't, the cl is partially correct;
  # If not all the builds have been triaged, the cl is partially triaged.
  for build in suspected_cl.builds.values():
    if build['status'] is None:
      partial_triaged = True
    elif build['status'] == suspected_cl_status.CORRECT:
      cl_incorrect = False
    else:
      cl_correct = False

  if partial_triaged:
    suspected_cl.status = suspected_cl_status.PARTIALLY_TRIAGED
  elif cl_correct:
    suspected_cl.status = suspected_cl_status.CORRECT
  elif cl_incorrect:
    suspected_cl.status = suspected_cl_status.INCORRECT
  else:
    suspected_cl.status = suspected_cl_status.PARTIALLY_CORRECT

  suspected_cl.updated_time = updated_time or time_util.GetUTCNow()

  suspected_cl.put()
  return True


@ndb.transactional
def _UpdateAnalysis(
    master_name, builder_name, build_number, repo_name, revision, cl_status):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis or not analysis.suspected_cls:
    return False

  num_correct = 0
  num_incorrect = 0
  for cl in analysis.suspected_cls:
    if cl['repo_name'] == repo_name and cl['revision'] == revision:
      # Updates this cl's status.
      cl['status'] = cl_status

    # Checks if all the cls have been triaged and checks the status of each cl
    # on the build.
    if cl.get('status') == suspected_cl_status.CORRECT:
      num_correct += 1
    elif cl.get('status') == suspected_cl_status.INCORRECT:
      num_incorrect += 1

  if num_correct + num_incorrect == len(analysis.suspected_cls):  # All triaged.
    if num_correct == 0:
      analysis.result_status = result_status.FOUND_INCORRECT
    elif num_incorrect == 0:
      analysis.result_status = result_status.FOUND_CORRECT
    else:
      analysis.result_status = result_status.PARTIALLY_CORRECT_FOUND

  analysis.put()
  return True


def _AppendTriageHistoryRecord(
    master_name, builder_name, build_number, cl_info, cl_status, user_name):

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:  # pragma: no cover
    return

  triage_record = {
      'triage_timestamp': time_util.GetUTCNowTimestamp(),
      'user_name': user_name,
      'cl_status': cl_status,
      'version': analysis.version,
      'triaged_cl': cl_info
  }
  if not analysis.triage_history:
    analysis.triage_history = []
  analysis.triage_history.append(triage_record)
  analysis.triage_email_obscured = False
  analysis.triage_record_last_add = time_util.GetUTCNow()

  analysis.put()


def _UpdateSuspectedCLAndAnalysis(
    master_name, builder_name, build_number, cl_info, cl_status, user_name):
  repo_name, revision  = GetCLInfo(cl_info)
  build_key = build_util.CreateBuildId(
      master_name, builder_name, build_number)

  success = (
      _UpdateSuspectedCL(repo_name, revision, build_key, cl_status) and
      _UpdateAnalysis(master_name, builder_name, build_number,
                      repo_name, revision, cl_status))

  if success:
    _AppendTriageHistoryRecord(
        master_name, builder_name, build_number, cl_info, cl_status, user_name)

  return success


class TriageSuspectedCl(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER
  LOGIN_REDIRECT_TO_DISTINATION_PAGE_FOR_GET = False

  def HandleGet(self):  # pragma: no cover
    """Sets the manual triage result for the cl."""
    url = self.request.get('url').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return {'data': {'success': False}}
    master_name, builder_name, build_number = build_info

    cl_status = int(self.request.get('status'))
    cl_info = self.request.get('cl_info')
    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]
    success = _UpdateSuspectedCLAndAnalysis(
      master_name, builder_name, build_number, cl_info, cl_status, user_name)

    return {'data': {'success': success}}


  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
