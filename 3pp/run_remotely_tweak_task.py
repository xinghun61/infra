# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import sys

d = json.load(sys.stdin)
# Remove all but the last slice to remove the ones with named caches as
# dimensions.
d['job_slices'][:] = [d['job_slices'][-1]]
json.dump(d, sys.stdout)
