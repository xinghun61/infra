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
MAXIMUM_QUERY_SIZE = 1000
VALID_EMAIL_RE = re.compile(r'^.*@(chromium\.org|google\.com)$')
