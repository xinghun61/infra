# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import sys

# pylint: disable=line-too-long

d = json.load(sys.stdin)
if not d['issue_url']:
  print >> sys.stderr, "Failed to get Gerrit CL associated with this repo."
  print >> sys.stderr, "Ensure that you've run `git cl upload` before using run_remotely.sh"
  sys.exit(1)
print d['issue_url']
