#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from infra.tools.cq_stats import cq_stats


if __name__ == '__main__':
  sys.exit(cq_stats.main())
