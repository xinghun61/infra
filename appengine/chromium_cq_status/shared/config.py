# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

AUTO_TAGGED_FIELDS = (
  'issue',
  'owner',
  'patchset',
  'project',
  'verification',
)
CQ_BOT_PASSWORD_KEY = 'cq_bot'
LAST_CQ_STATS_INTERVAL_CHANGE_KEY = 'last_cqstats_interval_minutes_%s_change'
LAST_CQ_STATS_CHANGE_KEY = 'last_cqstats_change'
DEFAULT_QUERY_SIZE = 100
MAXIMUM_QUERY_SIZE = 1000
# This mapping matches PatchSet.try_job_results() in the chromium_rietveld repo.
RIETVELD_JOB_STATE = {
  -1: 'running',
  0: 'passed',
  2: 'failed',
  # 6 is intended to be a value internal to Rietveld,
  # we should not depend on it here.
  # 6: 'trypending',
}
RIETVELD_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
STATS_START_TIMESTAMP = 374400 # 1970-01-05T00:00-0800 (midnight Monday PST)
TAG_START = 'action=patch_start'
TAG_STOP = 'action=patch_stop'
TAG_PROJECT = 'project=%s'
TAG_ISSUE = 'issue=%s'
TAG_PATCHSET = 'patchset=%s'
TRYJOBVERIFIER = 'simple try job'
VALID_EMAIL_RE = re.compile(r'^.*@(chromium\.org|google\.com)$')
