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
DEFAULT_QUERY_SIZE = 100
DEFAULT_STATS_VIEW_DAYS = 100
MAXIMUM_QUERY_SIZE = 1000
STATS_START_TIMESTAMP = 374400 # 1970-01-05T00:00-0800 (midnight Monday PST)
TRYJOBVERIFIER = 'simple try job'
VALID_EMAIL_RE = re.compile(r'^.*@(chromium\.org|google\.com)$')
