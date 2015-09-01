#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# See common.py for documentation

import sys

from infra.tools.send_ts_mon_values import common

if __name__ == '__main__':
  sys.exit(common.main(sys.argv[1:]))
