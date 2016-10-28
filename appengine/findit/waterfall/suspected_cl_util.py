# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import time_util
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_util


def GetCLInfo(cl_info_str):
  """Gets CL's repo_name and revision."""
  return cl_info_str.split('/')


def _GetsStatusFromSameFailure(builds, failures):
  for build in builds.values():
    if build['status'] is not None and build['failures'] == failures:
      return build['status']
  return None


@ndb.transactional
def UpdateSuspectedCL(
  repo_name, revision, commit_position,
  approach, master_name, builder_name, build_number, cl_failure_type,
  failures, top_score):

  suspected_cl = (
      WfSuspectedCL.Get(repo_name, revision) or
      WfSuspectedCL.Create(repo_name, revision, commit_position))

  if not suspected_cl.identified_time:  # pragma: no cover.
    suspected_cl.identified_time = time_util.GetUTCNow()

  suspected_cl.updated_time = time_util.GetUTCNow()

  if approach not in suspected_cl.approaches:
    suspected_cl.approaches.append(approach)
  if cl_failure_type not in suspected_cl.failure_type:
    suspected_cl.failure_type.append(cl_failure_type)

  build_key = build_util.CreateBuildId(
      master_name, builder_name, build_number)
  if build_key not in suspected_cl.builds:
    suspected_cl.builds[build_key] = {
        'approaches': [approach],
        'failure_type': cl_failure_type,
        'failures': failures,
        'status': _GetsStatusFromSameFailure(suspected_cl.builds, failures),
        'top_score': top_score
    }
  else:
    build = suspected_cl.builds[build_key]
    if approach not in build['approaches']:
      build['approaches'].append(approach)

  suspected_cl.put()
