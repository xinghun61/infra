# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Checks grouping for compile failures."""

from collections import defaultdict
from datetime import datetime
import json
import os
import sys

_REMOTE_API_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)
# Active script for Findit production.
from local_libs import remote_api
remote_api.EnableFinditRemoteApi()

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob


def _DisplayResults(groups_with_different_results, groups):
  results = {
      'groups_with_different_results': {
          'count': len(groups_with_different_results),
          'groups_with_different_results': groups_with_different_results
      },
      'groups': {
          'count': len(groups),
          'groups': groups
      }
  }
  print json.dumps(results, indent=2)


def main():
  start = datetime(2017, 12, 1, 0, 0, 0)
  cursor = None
  more = True

  groups_with_different_results = defaultdict(list)
  groups = defaultdict(list)

  while more:
    analyses, cursor, more = WfAnalysis.query(
        WfAnalysis.build_start_time >= start).fetch_page(
            100, start_cursor=cursor)

    for analysis in analyses:
      if (analysis.status != analysis_status.COMPLETED or
          not analysis.failure_group_key or
          analysis.failure_type != failure_type.COMPILE):
        continue

      group_key = '/'.join(str(x) for x in analysis.failure_group_key)
      culprit = None
      try_job = WfTryJob.Get(*analysis.key.pairs()[0][1].split('/'))
      if try_job and try_job.compile_results:
        culprit = try_job.compile_results[-1].get('culprit')

      same_result = False
      for item in groups[group_key]:
        if (item['culprit'] != culprit or
            item['suspects'] != analysis.suspected_cls):
          continue
        same_result = True
        item['builds'].append(analysis.key.pairs()[0][1])
        break

      if same_result:
        continue

      new_result = {
          'suspects': analysis.suspected_cls,
          'culprit': culprit,
          'builds': [analysis.key.pairs()[0][1]]
      }
      groups[group_key].append(new_result)

  for key, item in groups.iteritems():
    if len(item) > 1:
      groups_with_different_results[key] = item

  _DisplayResults(groups_with_different_results, groups)


if __name__ == '__main__':
  main()
